from pathlib import Path
from types import SimpleNamespace

from emumanager.gui_main import MainWindowBase
from emumanager.library import LibraryDB


class DummyItem:
    def __init__(self, text: str):
        self._text = text

    def text(self):
        return self._text


class DummyList:
    def __init__(self, items):
        self._items = items

    def selectedItems(self):
        return self._items


def test_gui_rename_writes_renamed_action(tmp_path: Path):
    # Arrange: create a fake ROM file under roms/<system>
    base = tmp_path
    system = "ps2"
    roms_dir = base / "roms" / system
    roms_dir.mkdir(parents=True)
    rom = roms_dir / "test_game.iso"
    rom.write_bytes(b"dummy")

    # Use a temporary DB file so we don't touch the project's DB
    db_path = base / "library_test.db"
    db = LibraryDB(db_path)

    # Build a lightweight MainWindowBase-like instance without invoking full __init__
    mw = MainWindowBase.__new__(MainWindowBase)
    mw.library_db = db
    messages = []
    mw.log_msg = lambda m: messages.append(m)
    mw.rom_list = DummyList([DummyItem(rom.name)])
    mw.sys_list = SimpleNamespace(
        currentItem=lambda: SimpleNamespace(text=lambda: system)
    )
    mw._manager = SimpleNamespace(get_roms_dir=lambda last_base: base / "roms")
    mw._last_base = base
    mw._populate_roms = lambda s: None
    mw._update_dashboard_stats = lambda: None

    # Monkeypatch the per-system rename helper so GUI thinks the rename succeeded
    mw._rename_single_to_standard = lambda sys, root, fp: True

    # Wrap log_action to detect calls and still persist
    orig_log = db.log_action
    called = {"v": False}

    def spy_log(path, action, detail=None):
        called["v"] = True
        return orig_log(path, action, detail)

    db.log_action = spy_log
    mw.library_db = db

    # Act
    mw.on_rename_to_standard_selected()

    # If log_action wasn't called, capture any log messages for debugging
    if not called["v"]:
        # attach messages to assertion output
        print("GUI log messages:")
        for msg in messages:
            print(msg)

    # Assert: log_action was called and DB contains a RENAMED action for our file
    assert called["v"], "library_db.log_action was not called"
    actions = db.get_actions(20)
    assert any(a[1] == "RENAMED" and Path(a[0]).name == rom.name for a in actions)
