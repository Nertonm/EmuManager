from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from emumanager.common.formatting import human_readable_size
from emumanager.library import LibraryDB
from emumanager.workers.duplicates import worker_find_duplicates

if TYPE_CHECKING:
    from emumanager.gui_main import MainWindowBase


class DuplicatesController:
    def __init__(self, main_window: MainWindowBase):
        self.mw = main_window
        self.ui = main_window.ui
        self._groups: list[dict[str, Any]] = []
        self._current_group: dict[str, Any] | None = None
        self._connect_signals()

    def _get_qt_constants(self):
        """Helper to resolve Qt constants across different versions/wrappers."""
        qt_enum = getattr(self.mw, "_Qt_enum", None)
        qtcore = getattr(self.mw, "_qtcore", None)
        
        class QtConstants:
            def __init__(self, enum, core):
                self.enum = enum
                self.core = core
                
            @property
            def checked(self):
                return self.enum.CheckState.Checked if self.enum else self.core.Qt.Checked
                
            @property
            def unchecked(self):
                return self.enum.CheckState.Unchecked if self.enum else self.core.Qt.Unchecked
                
            @property
            def item_is_user_checkable(self):
                return self.enum.ItemFlag.ItemIsUserCheckable if self.enum else self.core.Qt.ItemIsUserCheckable
                
            @property
            def user_role(self):
                if self.enum and hasattr(self.enum, "ItemDataRole"):
                    return self.enum.ItemDataRole.UserRole
                return self.core.Qt.UserRole if self.core else 256

            def get_alignment(self):
                if self.core:
                    return self.core.Qt.AlignRight | self.core.Qt.AlignVCenter
                if self.enum:
                    return self.enum.AlignmentFlag.AlignRight | self.enum.AlignmentFlag.AlignVCenter
                return None

        return QtConstants(qt_enum, qtcore)

    def _connect_signals(self):
        if hasattr(self.ui, "btn_dups_scan"):
            self.ui.btn_dups_scan.clicked.connect(self.scan_duplicates)
        if hasattr(self.ui, "list_dups_groups"):
            self.ui.list_dups_groups.currentItemChanged.connect(self._on_group_selected)

        if hasattr(self.ui, "btn_dups_keep_largest"):
            self.ui.btn_dups_keep_largest.clicked.connect(
                lambda: self._auto_pick("largest")
            )
        if hasattr(self.ui, "btn_dups_keep_smallest"):
            self.ui.btn_dups_keep_smallest.clicked.connect(
                lambda: self._auto_pick("smallest")
            )

        if hasattr(self.ui, "btn_dups_open_location"):
            self.ui.btn_dups_open_location.clicked.connect(self._open_selected_location)

        if hasattr(self.ui, "btn_dups_move_others"):
            self.ui.btn_dups_move_others.clicked.connect(
                self._move_others_to_duplicates
            )
            self.ui.btn_dups_move_others.setEnabled(True)

    def _get_keep_rows(self) -> list[int]:
        if not hasattr(self.ui, "table_dups_entries"):
            return []
        table = self.ui.table_dups_entries
        keep: list[int] = []
        for r in range(table.rowCount()):
            it = table.item(r, 0)
            if not it:
                continue
            # Use getattr guards to avoid attribute access on None for static checkers
            qt_enum = getattr(self.mw, "_Qt_enum", None)
            qtcore = getattr(self.mw, "_qtcore", None)
            try:
                if qt_enum is not None:
                    checked = it.checkState() == qt_enum.CheckState.Checked
                elif qtcore is not None:
                    checked = it.checkState() == qtcore.Qt.Checked
                else:
                    checked = False
            except Exception:
                checked = False
            if checked:
                keep.append(r)
        return keep

    def _unique_dest_path(self, dest: Path) -> Path:
        """Return a collision-safe destination path.

        We want a deterministic, readable name in duplicates/:
        - first try the original name
        - then append __dupN before the suffix.
        """
        if not dest.exists():
            return dest
        parent = dest.parent
        stem = dest.stem
        suffix = dest.suffix
        for i in range(1, 10_000):
            cand = parent / f"{stem}__dup{i}{suffix}"
            if not cand.exists():
                return cand
        raise RuntimeError(f"Unable to find unique destination for {dest.name}")

    def _resolve_duplicates_root(self) -> Path:
        base = self.mw._last_base
        if not base:
            raise RuntimeError("No library base selected")
        base = Path(base)
        # base may be .../roms or the project root depending on how user opened.
        # We always want duplicates folder next to 'roms' directory if possible.
        if base.name == "roms":
            return base.parent / "duplicates"
        # if base contains 'roms' child, place duplicates alongside it.
        if (base / "roms").exists():
            return base / "duplicates"
        # fallback: put under base
        return base / "duplicates"

    def _validate_move_selection(self) -> Optional[int]:
        if not self._current_group:
            self.mw.log_msg("No duplicate group selected")
            return None

        keep_rows = self._get_keep_rows()
        if len(keep_rows) != 1:
            self.mw.log_msg("Please select exactly ONE file to keep (check the Keep? box).")
            return None
        return keep_rows[0]

    def _gather_duplicate_moves(self, keep_row: int) -> list[tuple[Path, Path, str]]:
        table = self.ui.table_dups_entries
        moves: list[tuple[Path, Path, str]] = []
        duplicates_root = self._resolve_duplicates_root()

        for r in range(table.rowCount()):
            if r == keep_row:
                continue
            path_item = table.item(r, 4)
            sys_item = table.item(r, 1)
            if not path_item or not sys_item:
                continue
            src = Path(path_item.text())
            system = str(sys_item.text() or "unknown")
            if src.exists():
                dst = duplicates_root / system / src.name
                moves.append((src, dst, system))
        return moves

    def _execute_duplicate_move(self, src: Path, dst: Path, args: Any, db: LibraryDB, logger: logging.Logger) -> tuple[bool, str]:
        from emumanager.common.fileops import safe_move as _safe_move

        def _fast_hash(p: Path) -> str:
            try:
                st = p.stat()
                return f"{st.st_size}:{int(st.st_mtime)}"
            except Exception:
                return "0:0"

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            chosen = self._unique_dest_path(dst)
            if _safe_move(src, chosen, args=args, get_file_hash=_fast_hash, logger=logger):
                self._remove_from_db(db, src)
                return True, str(chosen)
            return False, str(src)
        except Exception as e:
            logger.error(f"Failed to move {src}: {e}")
            return False, f"{src} ({e})"

    def _remove_from_db(self, db: LibraryDB, path: Path):
        try:
            db.remove_entry(str(path.resolve()))
        except Exception:
            try:
                db.remove_entry(str(path))
            except Exception as e:
                logging.debug(f"DB removal failed for {path}: {e}")

    def _do_duplicate_move_work(self, moves: list, dry_run_flag: bool) -> dict:
        moved, skipped = [], []
        db = self.mw.library_db
        logger = getattr(self.mw, "logger", None) or logging.getLogger(__name__)

        class _Args:
            dry_run = dry_run_flag
            dup_check = "fast"

        for src, dst, _ in moves:
            ok, info = self._execute_duplicate_move(src, dst, _Args, db, logger)
            if ok:
                moved.append((str(src), info))
            else:
                skipped.append(info)
        return {"moved": moved, "skipped": skipped}

    def _on_duplicate_move_finished(self, result: Any):
        if isinstance(result, Exception):
            self.mw.log_msg(f"Move duplicates error: {result}")
            return
        
        moved = result.get("moved", [])
        skipped = result.get("skipped", [])
        self.mw.log_msg(f"Move complete. Moved: {len(moved)} | Skipped: {len(skipped)}")
        
        if skipped:
            self.mw.log_msg("Some files were skipped:")
            for s in skipped[:30]: 
                self.mw.log_msg(f" - {s}")
        
        try:
            self.scan_duplicates()
        except Exception as e:
            logging.debug(f"Refresh failed: {e}")

    def _move_others_to_duplicates(self):
        keep_row = self._validate_move_selection()
        if keep_row is None:
            return

        table = self.ui.table_dups_entries
        keep_path_item = table.item(keep_row, 4)
        if not keep_path_item or not Path(keep_path_item.text()).exists():
            self.mw.log_msg("Selected keep file no longer exists or path is missing")
            return

        moves = self._gather_duplicate_moves(keep_row)
        if not moves:
            self.mw.log_msg("Nothing to move (only one file in group?)")
            return

        dry_run_flag = False
        try:
            dry_run_flag = bool(self.mw.chk_dry_run.isChecked())
        except Exception as e:
            logging.debug(f"Could not read dry run flag: {e}")

        duplicates_root = self._resolve_duplicates_root()
        self.mw.log_msg(f"Moving {len(moves)} file(s) to {duplicates_root} (dry_run={dry_run_flag})...")

        self.mw._run_in_background(
            lambda: self._do_duplicate_move_work(moves, dry_run_flag), 
            self._on_duplicate_move_finished
        )

    def _update_dups_summary(self, result: dict):
        total_groups = int(result.get("total_groups", 0))
        total_items = int(result.get("total_items", 0))
        wasted = int(result.get("wasted_bytes", 0))

        if hasattr(self.ui, "lbl_dups_summary"):
            wasted_mb = wasted / 1024 / 1024
            self.ui.lbl_dups_summary.setText(
                f"Groups: {total_groups} | Items: {total_items} | Wasted: {wasted_mb:.1f} MB"
            )

    def _add_group_list_item(self, group: dict):
        kind = group.get("kind", "?")
        count = group.get("count", 0)
        wasted_g = int(group.get("wasted_bytes", 0))
        key = str(group.get("key", ""))
        key_short = key if len(key) <= 18 else key[:18] + "…"
        text = f"[{kind}] x{count} wasted {human_readable_size(wasted_g)} — {key_short}"
        
        item = self.mw._qtwidgets.QListWidgetItem(text)
        item.setToolTip(key)
        self.ui.list_dups_groups.addItem(item)

    def scan_duplicates(self):
        if not self.mw._last_base:
            self.mw.log_msg("Please select a base directory first (Open Library).")
            return

        include_name = True
        if hasattr(self.ui, "chk_dups_include_name"):
            include_name = bool(self.ui.chk_dups_include_name.isChecked())
        
        filter_non_games = True
        if hasattr(self.ui, "chk_dups_filter_non_games"):
            filter_non_games = bool(self.ui.chk_dups_filter_non_games.isChecked())

        self.ui.list_dups_groups.clear()
        self._groups, self._current_group = [], None
        self._clear_entries_table()
        self.mw.log_msg("Scanning duplicates...")

        progress_cb = self.mw._signaler.progress_signal.emit if self.mw._signaler else None

        def _work():
            return worker_find_duplicates(
                db=self.mw.library_db,
                log_cb=self.mw.log_msg,
                progress_cb=progress_cb,
                cancel_event=self.mw._cancel_event,
                include_name=include_name,
                filter_non_games=filter_non_games,
            )

        def _done(result):
            if isinstance(result, Exception):
                self.mw.log_msg(f"Duplicate scan error: {result}")
                return

            self._groups = result.get("groups", [])
            self._update_dups_summary(result)
            for g in self._groups:
                self._add_group_list_item(g)

        self.mw._run_in_background(_work, _done)

    def _on_group_selected(self, current, previous=None):
        if not current:
            self._current_group = None
            self._clear_entries_table()
            return

        row = self.ui.list_dups_groups.currentRow()
        if row < 0 or row >= len(self._groups):
            self._current_group = None
            self._clear_entries_table()
            return

        group = self._groups[row]
        self._current_group = group
        self._render_group(group)

    def _clear_entries_table(self):
        if not hasattr(self.ui, "table_dups_entries"):
            return
        self.ui.table_dups_entries.setRowCount(0)

    def _create_table_entry_items(self, entry: dict, row: int):
        qt = self._get_qt_constants()
        
        chk = self.mw._qtwidgets.QTableWidgetItem("")
        try:
            chk.setFlags(chk.flags() | qt.item_is_user_checkable)
            chk.setCheckState(qt.unchecked)
        except Exception as e:
            logging.debug(f"Failed to set check flags: {e}")

        system_item = self.mw._qtwidgets.QTableWidgetItem(str(entry.get("system", "")))
        file_item = self.mw._qtwidgets.QTableWidgetItem(Path(entry.get("path", "")).name)
        
        size_bytes = int(entry.get("size", 0))
        size_item = self.mw._qtwidgets.QTableWidgetItem(human_readable_size(size_bytes))
        try:
            size_item.setData(qt.user_role, size_bytes)
            align = qt.get_alignment()
            if align:
                size_item.setTextAlignment(align)
            size_item.setToolTip(f"{size_bytes} bytes")
        except Exception as e:
            logging.debug(f"Failed to set size item data: {e}")

        path_item = self.mw._qtwidgets.QTableWidgetItem(str(entry.get("path", "")))
        
        items = [chk, system_item, file_item, size_item, path_item]
        for col, item in enumerate(items):
            self.ui.table_dups_entries.setItem(row, col, item)

    def _render_group(self, group: dict[str, Any]):
        entries = group.get("entries", [])
        table = self.ui.table_dups_entries
        table.setRowCount(0)

        for i, e in enumerate(entries):
            table.insertRow(i)
            self._create_table_entry_items(e, i)

        if entries:
            self._auto_pick("largest", silent=True)

    def _auto_pick(self, mode: str, silent: bool = False):
        if not self._current_group:
            return
        
        entries = self._current_group.get("entries", [])
        if not entries:
            return

        qt = self._get_qt_constants()
        table = self.ui.table_dups_entries
        
        for r in range(table.rowCount()):
            it = table.item(r, 0)
            if it:
                try:
                    it.setCheckState(qt.unchecked)
                except Exception as e:
                    logging.debug(f"Failed to uncheck: {e}")

        pick_row = max(0, table.rowCount() - 1) if mode == "smallest" else 0
        it = table.item(pick_row, 0)
        if it:
            try:
                it.setCheckState(qt.checked)
            except Exception as e:
                logging.debug(f"Failed to check: {e}")

        if not silent:
            self.mw.log_msg(f"Selected keep={mode} (row {pick_row + 1})")

    def _open_selected_location(self):
        table = self.ui.table_dups_entries
        row = table.currentRow()
        if row < 0:
            return
        path_item = table.item(row, 4)
        if not path_item:
            return
        p = Path(path_item.text())
        if p.exists():
            self.mw._open_file_location(p)
        else:
            logging.info("Selected path no longer exists")
