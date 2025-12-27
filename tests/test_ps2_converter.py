import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import ps2_converter


def test_missing_tools(monkeypatch, tmp_path):
    # Simulate no tools in PATH
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError):
        ps2_converter.convert_directory(directory=tmp_path)


def test_happy_path(monkeypatch, tmp_path):
    # Prepare a fake .cso file
    cso = tmp_path / "GameTitle.cso"
    cso.write_text("dummy")

    # Mock which to return fake paths for tools
    def fake_which(name: str):
        if name == "maxcso":
            return "/usr/bin/maxcso"
        if name == "chdman":
            return "/usr/bin/chdman"
        return None

    monkeypatch.setattr(shutil, "which", fake_which)

    # Mock subprocess.run to create ISO/CHD files when called
    def fake_run(cmd, capture_output=True, text=True, timeout=None, **kwargs):
        cmd_s = " ".join(cmd)
        if "maxcso" in cmd_s:
            # create iso file
            out_idx = cmd.index("-o") + 1
            iso_path = Path(cmd[out_idx])
            iso_path.write_text("iso")
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
        if "chdman" in cmd_s:
            out_idx = cmd.index("-o") + 1
            chd_path = Path(cmd[out_idx])
            chd_path.write_text("chd")
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Run conversion
    backup = tmp_path / "_LIXO_CSO"
    results = ps2_converter.convert_directory(
        directory=tmp_path, dry_run=False, backup_dir=backup, verbose=True
    )

    assert len(results) == 1
    res = results[0]
    assert res.success is True
    # CHD was created
    assert (tmp_path / "GameTitle.chd").exists()
    # Original CSO moved to backup
    assert (backup / "GameTitle.cso").exists()


def test_remove_original(monkeypatch, tmp_path):
    # Prepare a fake .cso file
    cso = tmp_path / "RemoveMe.cso"
    cso.write_text("dummy")

    def fake_which(name: str):
        if name == "maxcso":
            return "/usr/bin/maxcso"
        if name == "chdman":
            return "/usr/bin/chdman"
        return None

    monkeypatch.setattr(shutil, "which", fake_which)

    def fake_run(cmd, capture_output=True, text=True, timeout=None, **kwargs):
        cmd_s = " ".join(cmd)
        if "maxcso" in cmd_s:
            out_idx = cmd.index("-o") + 1
            iso_path = Path(cmd[out_idx])
            iso_path.write_text("iso")
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
        if "chdman" in cmd_s:
            out_idx = cmd.index("-o") + 1
            chd_path = Path(cmd[out_idx])
            chd_path.write_text("chd")
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Run conversion with remove_original=True
    results = ps2_converter.convert_directory(
        directory=tmp_path,
        dry_run=False,
        backup_dir=tmp_path / "_LIXO_CSO",
        verbose=True,
        remove_original=True,
    )

    assert len(results) == 1
    res = results[0]
    assert res.success is True
    # CHD was created
    assert (tmp_path / "RemoveMe.chd").exists()
    # Original CSO should be removed (not moved)
    assert not (tmp_path / "RemoveMe.cso").exists()
