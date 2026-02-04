import pytest
from pathlib import Path
from emumanager.common.system import default_ideal_filename

def test_default_ideal_filename_with_title_and_serial():
    path = Path("game.iso")
    meta = {"title": "God of War", "serial": "SCUS-97465"}
    assert default_ideal_filename(path, meta) == "God of War [SCUS-97465].iso"

def test_default_ideal_filename_only_title():
    path = Path("game.iso")
    meta = {"title": "God of War"}
    assert default_ideal_filename(path, meta) == "God of War.iso"

def test_default_ideal_filename_fallback_to_name():
    path = Path("Original Name.iso")
    meta = {}
    assert default_ideal_filename(path, meta) == "Original Name.iso"
