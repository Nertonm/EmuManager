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

    def _move_others_to_duplicates(self):
        group = self._current_group
        if not group:
            self.mw.log_msg("No duplicate group selected")
            return

        table = self.ui.table_dups_entries
        keep_rows = self._get_keep_rows()
        if len(keep_rows) != 1:
            self.mw.log_msg(
                "Please select exactly ONE file to keep (check the Keep? box)."
            )
            return

        keep_row = keep_rows[0]
        keep_path_item = table.item(keep_row, 4)
        if not keep_path_item:
            self.mw.log_msg("Selected keep row has no path")
            return

        keep_path = Path(keep_path_item.text())
        if not keep_path.exists():
            self.mw.log_msg("Selected keep file no longer exists")
            return

        # gather moves
        moves: list[tuple[Path, Path, str]] = []  # (src, dst, system)
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
            if not src.exists():
                continue
            dst_dir = duplicates_root / system
            dst = dst_dir / src.name
            moves.append((src, dst, system))

        if not moves:
            self.mw.log_msg("Nothing to move (only one file in group?)")
            return

        dry_run_flag = False
        try:
            dry_run_flag = bool(self.mw.chk_dry_run.isChecked())
        except Exception:
            dry_run_flag = False

        msg = (
            f"Moving {len(moves)} file(s) to {duplicates_root} "
            f"(dry_run={dry_run_flag})..."
        )
        self.mw.log_msg(msg)

        def _work():
            moved: list[tuple[str, str]] = []
            skipped: list[str] = []
            db: LibraryDB = self.mw.library_db

            # We reuse the project's safe_move helper to keep semantics consistent,
            # but we use a very lightweight hash fn (size+mtime) as collision checks
            # are already handled by unique filenames.
            from emumanager.common.fileops import safe_move as _safe_move

            class _Args:
                dry_run = dry_run_flag
                dup_check = "fast"

            def _fast_hash(p: Path) -> str:
                try:
                    st = p.stat()
                    return f"{st.st_size}:{int(st.st_mtime)}"
                except Exception:
                    return "0:0"

            logger = getattr(self.mw, "logger", None) or logging.getLogger(__name__)

            for src, dst, system in moves:
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    chosen = self._unique_dest_path(dst)
                    ok = _safe_move(
                        src, chosen, args=_Args, get_file_hash=_fast_hash, logger=logger
                    )
                    if ok:
                        moved.append((str(src), str(chosen)))
                        # Remove from active library index (it's now in duplicates)
                        try:
                            db.remove_entry(str(src.resolve()))
                        except Exception:
                            # DB may store non-resolved path; best-effort attempt
                            try:
                                db.remove_entry(str(src))
                            except Exception:
                                pass
                    else:
                        skipped.append(str(src))
                except Exception as e:
                    skipped.append(f"{src} ({e})")

            return {"moved": moved, "skipped": skipped}

        def _done(result):
            if isinstance(result, Exception):
                self.mw.log_msg(f"Move duplicates error: {result}")
                return

            moved = result.get("moved", []) if isinstance(result, dict) else []
            skipped = result.get("skipped", []) if isinstance(result, dict) else []
            self.mw.log_msg(
                f"Move complete. Moved: {len(moved)} | Skipped: {len(skipped)}"
            )
            if skipped:
                self.mw.log_msg("Some files were skipped:")
                for s in skipped[:30]:
                    self.mw.log_msg(f" - {s}")

            # Refresh duplicates view
            try:
                self.scan_duplicates()
            except Exception:
                pass

        self.mw._run_in_background(_work, _done)

    def scan_duplicates(self):
        if not self.mw._last_base:
            self.mw.log_msg("Please select a base directory first (Open Library).")
            return

        include_name = True
        if hasattr(self.ui, "chk_dups_include_name"):
            include_name = bool(self.ui.chk_dups_include_name.isChecked())
        filter_non_games = True
        if hasattr(self.ui, "chk_dups_filter_non_games"):
            # Checkbox label is 'Filter non-game files'. When checked,
            # we filter those files out.
            filter_non_games = bool(self.ui.chk_dups_filter_non_games.isChecked())

        self.ui.list_dups_groups.clear()
        self._groups = []
        self._current_group = None
        self._clear_entries_table()

        self.mw.log_msg("Scanning duplicates...")

        progress_cb = (
            self.mw._signaler.progress_signal.emit if self.mw._signaler else None
        )

        def _work():
            # Use the same DB instance the app is using
            db: LibraryDB = self.mw.library_db
            return worker_find_duplicates(
                db=db,
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

            groups = result.get("groups", []) if isinstance(result, dict) else []
            self._groups = groups

            total_groups = int(result.get("total_groups", 0))
            total_items = int(result.get("total_items", 0))
            wasted = int(result.get("wasted_bytes", 0))

            if hasattr(self.ui, "lbl_dups_summary"):
                wasted_mb = wasted / 1024 / 1024
                self.ui.lbl_dups_summary.setText(
                    f"Groups: {total_groups} | Items: {total_items} | "
                    f"Wasted: {wasted_mb:.1f} MB"
                )

            for g in groups:
                kind = g.get("kind", "?")
                count = g.get("count", 0)
                wasted_g = int(g.get("wasted_bytes", 0))
                key = str(g.get("key", ""))
                key_short = key if len(key) <= 18 else key[:18] + "…"
                text = (
                    f"[{kind}] x{count} wasted {human_readable_size(wasted_g)} "
                    f"— {key_short}"
                )
                item = self.mw._qtwidgets.QListWidgetItem(text)
                item.setToolTip(key)
                self.ui.list_dups_groups.addItem(item)

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

    def _render_group(self, group: dict[str, Any]):
        entries = group.get("entries", [])
        table = self.ui.table_dups_entries
        table.setRowCount(0)

        for i, e in enumerate(entries):
            table.insertRow(i)

            chk = self.mw._qtwidgets.QTableWidgetItem("")
            # Prefer the newer Qt enum objects when available, otherwise
            # fallback to legacy qtcore attributes. Use getattr to avoid
            # attribute access on None (satisfies static checkers).
            qt_enum = getattr(self.mw, "_Qt_enum", None)
            qtcore = getattr(self.mw, "_qtcore", None)
            try:
                if qt_enum is not None:
                    chk.setFlags(chk.flags() | qt_enum.ItemFlag.ItemIsUserCheckable)
                    chk.setCheckState(qt_enum.CheckState.Unchecked)
                elif qtcore is not None:
                    chk.setFlags(chk.flags() | qtcore.Qt.ItemIsUserCheckable)
                    chk.setCheckState(qtcore.Qt.Unchecked)
            except Exception:
                # last-resort: ignore if flags API isn't present
                pass

            system_item = self.mw._qtwidgets.QTableWidgetItem(str(e.get("system", "")))
            file_item = self.mw._qtwidgets.QTableWidgetItem(
                Path(e.get("path", "")).name
            )
            size_bytes = int(e.get("size", 0))
            size_item = self.mw._qtwidgets.QTableWidgetItem(
                human_readable_size(size_bytes)
            )
            # Store numeric size in UserRole so table sorting can sort by number
            # instead of by the formatted string.
            # Resolve UserRole constant in a safe way for both Qt6 and legacy
            qt_enum = getattr(self.mw, "_Qt_enum", None)
            qtcore = getattr(self.mw, "_qtcore", None)
            if qt_enum is not None and hasattr(qt_enum, "ItemDataRole"):
                user_role = qt_enum.ItemDataRole.UserRole
            else:
                try:
                    user_role = qtcore.Qt.UserRole if qtcore is not None else 256
                except Exception:
                    user_role = 256
            try:
                size_item.setData(user_role, size_bytes)
            except Exception:
                # fallback: ignore if setData isn't available
                pass

            # right-align the size column for better readability
            try:
                qt_enum = getattr(self.mw, "_Qt_enum", None)
                qtcore = getattr(self.mw, "_qtcore", None)
                if qtcore is not None:
                    align = qtcore.Qt.AlignRight | qtcore.Qt.AlignVCenter
                    size_item.setTextAlignment(align)
                elif qt_enum is not None:
                    align = (
                        qt_enum.AlignmentFlag.AlignRight
                        | qt_enum.AlignmentFlag.AlignVCenter
                    )
                    size_item.setTextAlignment(align)
            except Exception:
                pass
            try:
                size_item.setToolTip(f"{size_bytes} bytes")
            except Exception:
                pass
            path_item = self.mw._qtwidgets.QTableWidgetItem(str(e.get("path", "")))

            table.setItem(i, 0, chk)
            table.setItem(i, 1, system_item)
            table.setItem(i, 2, file_item)
            table.setItem(i, 3, size_item)
            table.setItem(i, 4, path_item)

        # default: keep the first row (largest) when available
        if entries:
            self._auto_pick("largest", silent=True)

    def _auto_pick(self, mode: str, silent: bool = False):
        group = self._current_group
        if not group:
            return

        entries = group.get("entries", [])
        if not entries:
            return

        table = self.ui.table_dups_entries
        # clear checks
        for r in range(table.rowCount()):
            it = table.item(r, 0)
            if not it:
                continue
            qt_enum = getattr(self.mw, "_Qt_enum", None)
            qtcore = getattr(self.mw, "_qtcore", None)
            try:
                if qt_enum is not None:
                    it.setCheckState(qt_enum.CheckState.Unchecked)
                elif qtcore is not None:
                    it.setCheckState(qtcore.Qt.Unchecked)
            except Exception:
                pass

        if mode == "largest":
            pick_row = 0
        elif mode == "smallest":
            pick_row = max(0, table.rowCount() - 1)
        else:
            pick_row = 0

        it = table.item(pick_row, 0)
        if it:
            qt_enum = getattr(self.mw, "_Qt_enum", None)
            qtcore = getattr(self.mw, "_qtcore", None)
            try:
                if qt_enum is not None:
                    it.setCheckState(qt_enum.CheckState.Checked)
                elif qtcore is not None:
                    it.setCheckState(qtcore.Qt.Checked)
            except Exception:
                pass

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
