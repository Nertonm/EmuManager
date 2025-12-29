import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import importlib.util

# Helper to import the script module
def import_script(name):
    spec = importlib.util.spec_from_file_location(name, f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

create_mock_roms = import_script("create_mock_roms")

def test_create_dummy_file(tmp_path):
    file_path = tmp_path / "test.bin"
    create_mock_roms.create_dummy_file(file_path, size_bytes=100)
    assert file_path.exists()
    assert file_path.stat().st_size == 100

def test_create_text_file(tmp_path):
    file_path = tmp_path / "test.txt"
    content = "Hello World"
    create_mock_roms.create_text_file(file_path, content)
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == content

@patch("emumanager.architect.main")
def test_main_default_args(mock_architect, tmp_path):
    # Mock sys.argv
    test_dir = tmp_path / "mock_lib"
    with patch.object(sys, "argv", ["create_mock_roms.py", str(test_dir)]):
        create_mock_roms.main()
    
    # Verify architect was called
    mock_architect.assert_called_once()
    
    # Verify some files were created
    roms = test_dir / "roms"
    assert (roms / "switch" / "Super Mario Odyssey [0100000000010000][v0].nsp").exists()
    assert (roms / "ps2" / "God of War (USA).iso").exists()
    assert (test_dir / "keys.txt").exists()

@patch("emumanager.architect.main")
def test_main_custom_dir(mock_architect, tmp_path):
    target = tmp_path / "custom_target"
    with patch.object(sys, "argv", ["create_mock_roms.py", str(target)]):
        create_mock_roms.main()
    
    assert target.exists()
    assert (target / "roms" / "gamecube" / "Metroid Prime.rvz").exists()
