from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from emumanager.architect import get_roms_dir
from emumanager.gui_covers import CoverDownloader
from emumanager.verification.hasher import calculate_hashes
from emumanager.workers.verification import worker_identify_single_file

if TYPE_CHECKING:
    from emumanager.gui_main import MainWindowBase


class GalleryController:
    def __init__(self, main_window: MainWindowBase):
        self.mw = main_window
        self.ui = main_window.ui
        self._connect_signals()

    def _get_context_menu_policy(self):
        """Helper to resolve ContextMenuPolicy across different Qt versions."""
        # Try Qt6 Enum
        try:
            if self.mw._Qt_enum and hasattr(self.mw._Qt_enum, "ContextMenuPolicy"):
                return self.mw._Qt_enum.ContextMenuPolicy.CustomContextMenu
        except AttributeError:
            pass

        # Try Qt5/Legacy Enum
        try:
            if self.mw._Qt_enum and hasattr(self.mw._Qt_enum, "CustomContextMenu"):
                return self.mw._Qt_enum.CustomContextMenu
        except AttributeError:
            pass

        # Try via qtcore directly
        if self.mw._qtcore:
            try:
                return self.mw._qtcore.Qt.ContextMenuPolicy.CustomContextMenu
            except AttributeError:
                try:
                    return self.mw._qtcore.Qt.CustomContextMenu
                except AttributeError:
                    pass
        return None

    def _connect_signals(self):
        if hasattr(self.ui, "combo_gallery_system"):
            self.ui.combo_gallery_system.currentIndexChanged.connect(
                self._on_gallery_system_changed
            )
        if hasattr(self.ui, "btn_gallery_refresh"):
            self.ui.btn_gallery_refresh.clicked.connect(self.populate_gallery)

        if hasattr(self.ui, "list_gallery"):
            policy = self._get_context_menu_policy()
            if policy is not None:
                self.ui.list_gallery.setContextMenuPolicy(policy)
                self.ui.list_gallery.customContextMenuRequested.connect(
                    self._on_gallery_context_menu
                )

    def _on_gallery_system_changed(self, index):
        self.populate_gallery()

    def populate_gallery(self):
        if not self.mw._last_base:
            return

        system = self.ui.combo_gallery_system.currentText()
        if not system:
            return

        self.ui.list_gallery.clear()
        logging.info(f"Populating gallery for {system}...")

        roms_dir = get_roms_dir(Path(self.mw._last_base)) / system
        if not roms_dir.exists():
            return

        files = self._list_files_recursive(roms_dir)

        # Cache dir root
        cache_dir_root = Path(self.mw._last_base) / ".covers"
        cache_dir_root.mkdir(exist_ok=True)

        # Default icon
        default_icon = self.ui._get_icon(self.mw._qtwidgets, "SP_FileIcon")

        # Connection type for thread safety
        conn_type = (
            self.mw._Qt_enum.ConnectionType.QueuedConnection
            if self.mw._Qt_enum and hasattr(self.mw._Qt_enum, "ConnectionType")
            else self.mw._qtcore.Qt.QueuedConnection
        )

        for f in files:
            self._process_gallery_item(
                f, system, cache_dir_root, default_icon, conn_type
            )

        logging.info(f"Gallery population started for {len(files)} items.")

    def _process_gallery_item(
        self, f: Path, system: str, cache_dir_root: Path, default_icon, conn_type
    ):
        try:
            name = f.name
            item = self.mw._qtwidgets.QListWidgetItem(name)
            item.setToolTip(str(f))

            if default_icon:
                item.setIcon(default_icon)

            self.ui.list_gallery.addItem(item)

            # Trigger background check/download
            # Guess region
            region = None
            if "(USA)" in name or "(US)" in name:
                region = "US"
            elif "(Europe)" in name or "(EU)" in name:
                region = "EN"
            elif "(Japan)" in name or "(JP)" in name:
                region = "JA"

            downloader = CoverDownloader(
                system, None, region, str(cache_dir_root), str(f)
            )

            # Use partial to pass the item
            downloader.signals.finished.connect(
                partial(self._update_gallery_icon, item), conn_type
            )

            self.mw._qtcore.QThreadPool.globalInstance().start(downloader)

        except Exception as e:
            logging.error(f"Error adding gallery item {f}: {e}")

    def _update_gallery_icon(self, item, image_path):
        if not image_path or not Path(image_path).exists():
            return

        try:
            # Check if item is still valid (might have been cleared)
            if item.listWidget() is None:
                return

            icon = self.mw._qtgui.QIcon(image_path)
            item.setIcon(icon)
        except Exception:
            pass

    def _on_gallery_context_menu(self, position):
        item = self.ui.list_gallery.itemAt(position)
        if not item:
            return

        menu = self.mw._qtwidgets.QMenu()

        # Actions
        action_open = menu.addAction("Open File Location")
        action_verify = menu.addAction("Verify (Hash)")
        action_identify = menu.addAction("Identify with DAT...")
        menu.addSeparator()
        action_refresh_cover = menu.addAction("Redownload Cover")

        action = menu.exec(self.ui.list_gallery.mapToGlobal(position))

        if not action:
            return

        file_path = Path(item.toolTip())

        if action == action_open:
            self.mw._open_file_location(file_path)
        elif action == action_verify:
            self._verify_single_file(file_path)
        elif action == action_identify:
            self._identify_single_file_dialog(file_path)
        elif action == action_refresh_cover:
            self._refresh_gallery_cover(item, file_path)

    def _verify_single_file(self, file_path):
        logging.info(f"Verifying {file_path.name}...")

        def _work():
            return calculate_hashes(file_path)

        def _done(res):
            if res:
                msg = (
                    f"File: {file_path.name}\n\n"
                    f"CRC32: {res.crc32}\nMD5: {res.md5}\nSHA1: {res.sha1}"
                )
                self.mw._qtwidgets.QMessageBox.information(
                    self.mw.window, "Verification Result", msg
                )
                logging.info(f"Verified {file_path.name}: CRC32={res.crc32}")
            else:
                self.mw._qtwidgets.QMessageBox.warning(
                    self.mw.window, "Error", "Failed to calculate hashes."
                )

        self.mw._run_in_background(_work, _done)

    def _identify_single_file_dialog(self, file_path):
        dat_path, _ = self.mw._qtwidgets.QFileDialog.getOpenFileName(
            self.mw.window, "Select DAT File", "", "DAT Files (*.dat *.xml)"
        )
        if not dat_path:
            return

        logging.info(f"Identifying {file_path.name} using {Path(dat_path).name}...")

        def _work():
            return worker_identify_single_file(
                file_path, Path(dat_path), self.mw.log_msg, self.mw._progress_slot
            )

        def _done(res):
            logging.info(str(res))
            self.mw._qtwidgets.QMessageBox.information(
                self.mw.window, "Identification Result", str(res)
            )

        self.mw._run_in_background(_work, _done)

    def _refresh_gallery_cover(self, item, file_path):
        system = self.ui.combo_gallery_system.currentText()
        cache_dir_root = Path(self.mw._last_base) / ".covers"

        logging.info(f"Refreshing cover for {file_path.name}...")

        region = None
        name = file_path.name
        if "(USA)" in name or "(US)" in name:
            region = "US"
        elif "(Europe)" in name or "(EU)" in name:
            region = "EN"
        elif "(Japan)" in name or "(JP)" in name:
            region = "JA"

        downloader = CoverDownloader(
            system, None, region, str(cache_dir_root), str(file_path)
        )

        conn_type = (
            self.mw._Qt_enum.ConnectionType.QueuedConnection
            if self.mw._Qt_enum and hasattr(self.mw._Qt_enum, "ConnectionType")
            else self.mw._qtcore.Qt.QueuedConnection
        )
        downloader.signals.finished.connect(
            partial(self._update_gallery_icon, item), conn_type
        )
        self.mw._qtcore.QThreadPool.globalInstance().start(downloader)

    def _list_files_recursive(self, root: Path) -> list[Path]:
        files = []
        try:
            for p in root.rglob("*"):
                if p.is_file():
                    files.append(p)
        except Exception:
            pass
        return files
