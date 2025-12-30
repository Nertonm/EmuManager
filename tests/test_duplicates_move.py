from __future__ import annotations

from pathlib import Path

import pytest

from emumanager.controllers.duplicates import DuplicatesController


class _StubCheckBox:
    def __init__(self, checked: bool):
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


class _StubItem:
    def __init__(self, text: str):
        self._text = text

    def text(self) -> str:
        return self._text


class _StubTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._row_count = len(rows)

    def rowCount(self) -> int:
        return self._row_count

    def item(self, row: int, col: int):
        r = self._rows[row]
        if col == 0:
            return r.get("keep_item")
        if col == 1:
            return _StubItem(r["system"])
        if col == 4:
            return _StubItem(str(r["path"]))
        return None

    def currentRow(self) -> int:
        return 0


class _StubKeepItem:
    def __init__(self, checked: bool, mw):
        self._checked = checked
        self._mw = mw

    def checkState(self):
        # emulate Qt enum value
        return (
            self._mw._Qt_enum.CheckState.Checked
            if self._checked
            else self._mw._Qt_enum.CheckState.Unchecked
        )


class _StubQtEnum:
    class CheckState:
        Checked = 2
        Unchecked = 0


class _StubMW:
    def __init__(self, base: Path, table: _StubTable, dry_run: bool = False):
        self._last_base = base
        self._Qt_enum = _StubQtEnum
        self._qtcore = None
        self.chk_dry_run = _StubCheckBox(dry_run)
        self.ui = type("UI", (), {"table_dups_entries": table})()
        self.library_db = None
        self.logger = None
        self._cancel_event = None

        self._bg_work = None
        self._bg_done = None
        self.logs: list[str] = []

    def log_msg(self, msg: str):
        self.logs.append(msg)

    def _run_in_background(self, work, done):
        # run synchronously for unit test
        try:
            res = work()
        except Exception as e:  # pragma: no cover
            res = e
        done(res)


@pytest.mark.parametrize("base_is_roms", [True, False])
def test_move_others_to_duplicates(tmp_path: Path, base_is_roms: bool):
    # Layout
    root = tmp_path / "lib"
    roms = root / "roms"
    roms.mkdir(parents=True)

    base = roms if base_is_roms else root

    sys_dir = roms / "ps2"
    sys_dir.mkdir(parents=True)

    a = sys_dir / "A.iso"
    b = sys_dir / "B.iso"
    a.write_bytes(b"aaaa")
    b.write_bytes(b"bbbb")

    # destination duplicates root per controller rules
    expected_dups_root = root / "duplicates"

    # Build fake table (keep A)
    mw = _StubMW(
        base=base,
        table=_StubTable(
            [
                {"system": "ps2", "path": a, "keep_item": None},
                {"system": "ps2", "path": b, "keep_item": None},
            ]
        ),
        dry_run=False,
    )

    # fill keep items with mw enum
    mw.ui.table_dups_entries._rows[0]["keep_item"] = _StubKeepItem(True, mw)
    mw.ui.table_dups_entries._rows[1]["keep_item"] = _StubKeepItem(False, mw)

    # stub DB with remove_entry tracking
    class _DB:
        def __init__(self):
            self.removed: list[str] = []

        def remove_entry(self, path: str):
            self.removed.append(path)

    mw.library_db = _DB()

    ctrl = DuplicatesController(mw)
    ctrl._current_group = {"entries": [{"path": str(a)}, {"path": str(b)}]}

    ctrl._move_others_to_duplicates()

    # kept file stays
    assert a.exists()

    # moved file goes to duplicates/<system>/
    moved_path = expected_dups_root / "ps2" / "B.iso"
    assert moved_path.exists()
    assert not b.exists()

    # db was updated (best-effort)
    assert mw.library_db.removed


def test_move_requires_exactly_one_keep(tmp_path: Path):
    root = tmp_path / "lib"
    (root / "roms" / "wii").mkdir(parents=True)
    base = root

    a = root / "roms" / "wii" / "A.iso"
    b = root / "roms" / "wii" / "B.iso"
    a.write_bytes(b"aaaa")
    b.write_bytes(b"bbbb")

    mw = _StubMW(
        base=base,
        table=_StubTable(
            [
                {"system": "wii", "path": a, "keep_item": None},
                {"system": "wii", "path": b, "keep_item": None},
            ]
        ),
        dry_run=False,
    )
    mw.ui.table_dups_entries._rows[0]["keep_item"] = _StubKeepItem(False, mw)
    mw.ui.table_dups_entries._rows[1]["keep_item"] = _StubKeepItem(False, mw)

    mw.library_db = type("DB", (), {"remove_entry": lambda self, p: None})()

    ctrl = DuplicatesController(mw)
    ctrl._current_group = {"entries": [{"path": str(a)}, {"path": str(b)}]}

    ctrl._move_others_to_duplicates()

    # should not move anything
    assert a.exists()
    assert b.exists()
    assert any("exactly ONE" in m for m in mw.logs)
