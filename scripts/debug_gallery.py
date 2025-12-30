#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Ensure repo on path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# Headless
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets as qtwidgets  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from emumanager.controllers.gallery import GalleryController  # noqa: E402
from emumanager.gui_ui import Ui_MainWindow  # noqa: E402

# Create app
app = QApplication.instance() or QApplication([])
main_win = QMainWindow()
ui = Ui_MainWindow()
ui.setupUi(main_win, qtwidgets)


# Create test main window stub matching MainWindowBase attributes used
class TestMain:
    def __init__(self, ui, base):
        self.ui = ui
        self._qtwidgets = qtwidgets
        self._qtcore = __import__("PyQt6").QtCore
        self._qtgui = __import__("PyQt6").QtGui
        self._Qt_enum = None
        try:
            from PyQt6.QtCore import Qt as _Qt

            self._Qt_enum = _Qt
        except Exception:
            pass
        self._last_base = str(base)
        self.window = main_win
        self.library_db = None
        self._signaler = None

    def _run_in_background(self, work_fn, done_cb):
        res = work_fn()
        done_cb(res)

    def _get_list_files_fn(self):
        def lf(d):
            return []

        return lf

    def log_msg(self, m):
        print("LOG:", m)

    def _get_common_args(self):
        return type("A", (), {"rm_originals": False})()


# Create temporary image using Qt (avoid external deps)
base = Path(".").resolve() / "tmp_debug_gallery"
base.mkdir(exist_ok=True)
img = base / "cover.png"
pix = __import__("PyQt6").QtGui.QPixmap(64, 64)
pix.fill(__import__("PyQt6").QtGui.QColor(73, 109, 137))
pix.save(str(img))


# Fake LibraryDB
class DummyEntry:
    def __init__(self, path):
        self.path = str(path)


class DummyLibDB:
    def __init__(self, entries):
        self._entries = entries

    def get_entries_by_system(self, sys):
        return self._entries


# Place our test image into the expected cache location so the real
# CoverDownloader will find it quickly (avoids network calls).
cache_target = base / ".covers" / "covers" / "gamecube"
cache_target.mkdir(parents=True, exist_ok=True)
cached = cache_target / "demo.png"
if not cached.exists():
    # copy our generated pixmap image to the expected cache path
    Path(str(img)).replace(str(cached))

# Setup test main and gallery controller
test_main = TestMain(ui, base)
# set library db entries
entries = [DummyEntry(base / "roms" / "gamecube" / "demo.iso")]
# ensure path exists
(entries[0].path and Path(entries[0].path).parent.mkdir(parents=True, exist_ok=True))
entries[0].path = str(base / "roms" / "gamecube" / "demo.iso")
Path(entries[0].path).write_bytes(b"data")

test_main.library_db = DummyLibDB(entries)

# Fill combo and call populate
ui.combo_gallery_system.addItem("gamecube")
ui.combo_gallery_system.setCurrentIndex(0)

gc = GalleryController(test_main)

gc.populate_gallery()

# Check list item icons
for i in range(ui.list_gallery.count()):
    it = ui.list_gallery.item(i)
    print("Item:", it.text(), "HasIcon?:", not it.icon().isNull())

print("Done")
