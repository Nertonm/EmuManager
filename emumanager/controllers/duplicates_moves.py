from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from emumanager.library import LibraryDB

if TYPE_CHECKING:
    from emumanager.gui_main import MainWindowBase


class DuplicatesMoveMixin:
    mw: "MainWindowBase"
    ui: Any
    _current_group: dict[str, Any] | None

    def _get_keep_rows(self) -> list[int]:
        if not hasattr(self.ui, "table_dups_entries"):
            return []
        table = self.ui.table_dups_entries
        keep: list[int] = []
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if not item:
                continue
            qt_enum = getattr(self.mw, "_Qt_enum", None)
            qtcore = getattr(self.mw, "_qtcore", None)
            try:
                if qt_enum is not None:
                    checked = item.checkState() == qt_enum.CheckState.Checked
                elif qtcore is not None:
                    checked = item.checkState() == qtcore.Qt.Checked
                else:
                    checked = False
            except Exception:
                checked = False
            if checked:
                keep.append(row)
        return keep

    def _unique_dest_path(self, dest: Path) -> Path:
        """Return a collision-safe destination path."""
        if not dest.exists():
            return dest
        for index in range(1, 10_000):
            candidate = dest.parent / f"{dest.stem}__dup{index}{dest.suffix}"
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"Unable to find unique destination for {dest.name}")

    def _resolve_duplicates_root(self) -> Path:
        base = self.mw._last_base
        if not base:
            raise RuntimeError("No library base selected")

        base_path = Path(base)
        if base_path.name == "roms":
            return base_path.parent / "duplicates"
        if (base_path / "roms").exists():
            return base_path / "duplicates"
        return base_path / "duplicates"

    def _validate_move_selection(self) -> int | None:
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
        duplicates_root = self._resolve_duplicates_root()
        moves: list[tuple[Path, Path, str]] = []

        for row in range(table.rowCount()):
            if row == keep_row:
                continue
            path_item = table.item(row, 4)
            system_item = table.item(row, 1)
            if not path_item or not system_item:
                continue
            source = Path(path_item.text())
            system = str(system_item.text() or "unknown")
            if source.exists():
                moves.append((source, duplicates_root / system / source.name, system))
        return moves

    def _execute_duplicate_move(
        self,
        source: Path,
        dest: Path,
        args: Any,
        db: LibraryDB,
        logger: logging.Logger,
    ) -> tuple[bool, str]:
        def _fast_hash(path: Path) -> str:
            try:
                stat = path.stat()
                return f"{stat.st_size}:{int(stat.st_mtime)}"
            except Exception:
                return "0:0"

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            chosen_dest = self._unique_dest_path(dest)
            moved = self._safe_move(
                source,
                chosen_dest,
                args=args,
                get_file_hash=_fast_hash,
                logger=logger,
            )
            if moved:
                self._remove_from_db(db, source)
                return True, str(chosen_dest)
            return False, str(source)
        except Exception as exc:
            logger.error(f"Failed to move {source}: {exc}")
            return False, f"{source} ({exc})"

    def _remove_from_db(self, db: LibraryDB, path: Path):
        try:
            db.remove_entry(str(path.resolve()))
        except Exception:
            try:
                db.remove_entry(str(path))
            except Exception as exc:
                logging.debug(f"DB removal failed for {path}: {exc}")

    def _do_duplicate_move_work(self, moves: list, dry_run_flag: bool) -> dict:
        moved: list[tuple[str, str]] = []
        skipped: list[str] = []
        db = self.mw.library_db
        logger = getattr(self.mw, "logger", None) or logging.getLogger(__name__)

        class _Args:
            dry_run = dry_run_flag
            dup_check = "fast"

        for source, dest, _system in moves:
            ok, info = self._execute_duplicate_move(source, dest, _Args, db, logger)
            if ok:
                moved.append((str(source), info))
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
            for entry in skipped[:30]:
                self.mw.log_msg(f" - {entry}")

        try:
            self.mw._sync_after_verification()
        except Exception as exc:
            logging.debug(f"UI sync failed: {exc}")

        try:
            self.scan_duplicates()
        except Exception as exc:
            logging.debug(f"Refresh failed: {exc}")

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
        except Exception as exc:
            logging.debug(f"Could not read dry run flag: {exc}")

        duplicates_root = self._resolve_duplicates_root()
        self.mw.log_msg(
            f"Moving {len(moves)} file(s) to {duplicates_root} (dry_run={dry_run_flag})..."
        )
        self.mw._run_in_background(
            lambda: self._do_duplicate_move_work(moves, dry_run_flag),
            self._on_duplicate_move_finished,
        )
