from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import emumanager.workers.common as wc
import emumanager.workers.verification as wv
from emumanager.common.models import VerifyReport
from emumanager.verification import hasher
from emumanager.workers.verification import worker_hash_verify, worker_identify_all


class FakeDat:
    def lookup(self, crc=None, md5=None, sha1=None):
        return []


def make_args():
    return SimpleNamespace(progress_callback=None, deep_verify=False, system_name="ps2")


# Helper used by tests to simulate missing tools
def _fake_find_none(name):
    return None


def test_chd_extraction_success_logs(monkeypatch, tmp_path):
    # Prepare a fake CHD file
    f = tmp_path / "game.chd"
    f.write_bytes(b"chd")

    # Capture logger messages
    msgs = []

    def log_cb(m: str):
        msgs.append(m)

    eff_logger = wc.GuiLogger(log_cb)

    # Stub find_tool to pretend chdman exists
    def _fake_find_tool_chd(name):
        return Path("/usr/bin/chdman") if name == "chdman" else None

    monkeypatch.setattr(wc, "find_tool", _fake_find_tool_chd)

    # Stub run_cmd_stream to create the output ISO and return success
    def fake_run_cmd_stream(cmd, progress_cb=None, **kwargs):
        # assume last arg is the output path
        out = cmd[-1]
        Path(out).write_bytes(b"ISO")

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(wv, "run_cmd_stream", fake_run_cmd_stream)

    # Stub hasher to avoid heavy IO
    def _fake_calc(path, algorithms, progress_cb=None):
        return {"crc32": "c", "md5": "m", "sha1": "s"}

    monkeypatch.setattr(hasher, "calculate_hashes", _fake_calc)

    res = wv._verify_single_file(
        f,
        FakeDat(),
        make_args(),
        None,
        0.0,
        1.0,
        lib_db=None,
        logger=eff_logger,
    )
    assert res is not None

    # We should have logged attempt and success messages
    assert any("Attempting to extract CHD" in m for m in msgs)
    assert any("CHD extracted to temporary ISO" in m for m in msgs)


def test_chd_tool_missing_logs(monkeypatch, tmp_path):
    f = tmp_path / "game.chd"
    f.write_bytes(b"chd")

    msgs = []

    def log_cb(m: str):
        msgs.append(m)

    eff_logger = wc.GuiLogger(log_cb)

    # Stub find_tool to return None (tool missing)
    monkeypatch.setattr(wc, "find_tool", _fake_find_none)

    # Stub hasher to return some hashes so flow continues
    def _fake_calc2(path, algorithms, progress_cb=None):
        return {"crc32": "c", "md5": "m", "sha1": "s"}

    monkeypatch.setattr(hasher, "calculate_hashes", _fake_calc2)

    res = wv._verify_single_file(
        f,
        FakeDat(),
        make_args(),
        None,
        0.0,
        1.0,
        lib_db=None,
        logger=eff_logger,
    )
    assert res is not None

    # Should have logged that chdman was not found
    assert any("chdman" in m and "não encontrada" in m for m in msgs)


def test_cso_decompression_success_logs(monkeypatch, tmp_path):
    f = tmp_path / "game.cso"
    f.write_bytes(b"cso")

    msgs = []

    def log_cb(m: str):
        msgs.append(m)

    eff_logger = wc.GuiLogger(log_cb)

    def _fake_find_tool_max(name):
        return Path("/usr/bin/maxcso") if name == "maxcso" else None

    monkeypatch.setattr(wc, "find_tool", _fake_find_tool_max)

    def fake_run_cmd_stream(cmd, progress_cb=None, **kwargs):
        out = cmd[-1]
        Path(out).write_bytes(b"ISO")

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(wv, "run_cmd_stream", fake_run_cmd_stream)

    def _fake_calc3(path, algorithms, progress_cb=None):
        return {"crc32": "c", "md5": "m", "sha1": "s"}

    monkeypatch.setattr(hasher, "calculate_hashes", _fake_calc3)

    res = wv._verify_single_file(
        f,
        FakeDat(),
        make_args(),
        None,
        0.0,
        1.0,
        lib_db=None,
        logger=eff_logger,
    )
    assert res is not None

    assert any("Attempting to decompress CSO" in m for m in msgs)
    assert any("CSO decompressed to temporary ISO" in m for m in msgs)


def test_cso_tool_missing_logs(monkeypatch, tmp_path):
    f = tmp_path / "game.cso"
    f.write_bytes(b"cso")

    msgs = []

    def log_cb(m: str):
        msgs.append(m)

    eff_logger = wc.GuiLogger(log_cb)

    monkeypatch.setattr(wc, "find_tool", _fake_find_none)

    def _fake_calc4(path, algorithms, progress_cb=None):
        return {"crc32": "c", "md5": "m", "sha1": "s"}

    monkeypatch.setattr(hasher, "calculate_hashes", _fake_calc4)

    res = wv._verify_single_file(
        f,
        FakeDat(),
        make_args(),
        None,
        0.0,
        1.0,
        lib_db=None,
        logger=eff_logger,
    )
    assert res is not None

    assert any("maxcso" in m and "não encontrada" in m for m in msgs)


def test_chd_info_sha1_fallback_verified_logs(monkeypatch, tmp_path):
    # CHD extraction fails but chdman info contains a SHA1 that matches DAT
    f = tmp_path / "game.chd"
    f.write_bytes(b"chd")

    msgs = []

    def log_cb(m: str):
        msgs.append(m)

    eff_logger = wc.GuiLogger(log_cb)

    # Pretend chdman exists
    def _fake_find_tool_chd(name):
        return Path("/usr/bin/chdman") if name == "chdman" else None

    monkeypatch.setattr(wc, "find_tool", _fake_find_tool_chd)

    # Simulate extraction failure
    def fake_run_cmd_stream(cmd, progress_cb=None, **kwargs):
        class R:
            returncode = 1
            stdout = "extraction failed"

        return R()

    monkeypatch.setattr(wv, "run_cmd_stream", fake_run_cmd_stream)

    # Simulate chdman info returning a SHA1
    def fake_run_cmd(cmd, **kwargs):
        class R:
            stdout = "SHA1: a2955857e44088ea155b75fbaaa377ecf01571fd"

        return R()

    monkeypatch.setattr(wv, "run_cmd", fake_run_cmd)

    # Fake DAT that returns a matching entry for the SHA1
    class FakeDatMatch:
        def lookup(self, crc=None, md5=None, sha1=None):
            if sha1 and sha1.lower() == "a2955857e44088ea155b75fbaaa377ecf01571fd":
                return [SimpleNamespace(game_name="God of War", dat_name="GOW")]
            return []

    res = wv._verify_single_file(
        f,
        FakeDatMatch(),
        make_args(),
        None,
        0.0,
        1.0,
        lib_db=None,
        logger=eff_logger,
    )

    assert res is not None
    assert res.status == "VERIFIED"
    assert any("Found SHA1 in CHD header" in m for m in msgs)
    assert any("Verified via CHD header SHA1" in m for m in msgs)


def test_chd_info_sha1_fallback_no_match_logs(monkeypatch, tmp_path):
    # CHD extraction fails, chdman info contains SHA1 but DAT has no match -> COMPRESSED
    f = tmp_path / "game.chd"
    f.write_bytes(b"chd")

    msgs = []

    def log_cb(m: str):
        msgs.append(m)

    eff_logger = wc.GuiLogger(log_cb)

    monkeypatch.setattr(wc, "find_tool", lambda name: Path("/usr/bin/chdman") if name == "chdman" else None)

    def fake_run_cmd_stream(cmd, progress_cb=None, **kwargs):
        class R:
            returncode = 1
            stdout = "extraction failed"

        return R()

    monkeypatch.setattr(wv, "run_cmd_stream", fake_run_cmd_stream)

    def fake_run_cmd_no_match(cmd, **kwargs):
        class R:
            stdout = "SHA1: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

        return R()

    monkeypatch.setattr(wv, "run_cmd", fake_run_cmd_no_match)

    class FakeDatNoMatch:
        def lookup(self, crc=None, md5=None, sha1=None):
            return []

    res = wv._verify_single_file(
        f,
        FakeDatNoMatch(),
        make_args(),
        None,
        0.0,
        1.0,
        lib_db=None,
        logger=eff_logger,
    )

    assert res is not None
    assert res.status == "COMPRESSED"
    assert any("Found SHA1 in CHD header" in m for m in msgs)
    assert any("falling back to compressed status" in m for m in msgs)



@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.dat_path = None
    args.dats_roots = []
    args.dats_root = None
    return args


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.name = "TestDB"
    db.version = "1.0"
    return db


def test_worker_hash_verify_no_dat(tmp_path, mock_logger, mock_args):
    """Test verification when no DAT file is found."""
    # Setup base path with a system name
    base_path = tmp_path / "snes"
    base_path.mkdir()

    # Provide dats_roots so it attempts discovery and logs warning
    mock_args.dats_roots = [tmp_path / "dats"]

    report = worker_hash_verify(base_path, mock_args, mock_logger, lambda p: [])

    assert "Error: No valid DAT file selected or found" in report.text
    # Check for warning log
    assert any("WARN: " in str(call) for call in mock_logger.call_args_list)


def test_worker_hash_verify_auto_discovery(tmp_path, mock_logger, mock_args, mock_db):
    """Test auto-discovery of DAT file based on folder name."""
    base_path = tmp_path / "snes"
    base_path.mkdir()

    dats_root = tmp_path / "dats"
    dats_root.mkdir()
    dat_file = dats_root / "Nintendo - Super Nintendo Entertainment System.dat"
    dat_file.touch()

    mock_args.dats_roots = [dats_root]

    # Mock find_dat_for_system to return our dat file
    with (
        patch(
            "emumanager.workers.verification.find_dat_for_system", return_value=dat_file
        ),
        patch(
            "emumanager.workers.verification.dat_parser.parse_dat_file",
            return_value=mock_db,
        ),
        patch("emumanager.workers.verification._run_verification") as mock_run,
    ):
        mock_run.return_value = VerifyReport(text="Success")

        report = worker_hash_verify(base_path, mock_args, mock_logger, lambda p: [])

        assert report.text == "Success"
        mock_logger.assert_any_call(
            f"Auto-selected DAT: {dat_file.name} (in {dats_root})"
        )


def test_worker_hash_verify_parse_error(tmp_path, mock_logger, mock_args):
    """Test handling of DAT parsing errors."""
    base_path = tmp_path / "snes"
    dat_path = tmp_path / "snes.dat"
    dat_path.touch()
    mock_args.dat_path = dat_path

    with patch(
        "emumanager.workers.verification.dat_parser.parse_dat_file",
        side_effect=Exception("Parse Error"),
    ):
        report = worker_hash_verify(base_path, mock_args, mock_logger, lambda p: [])

        assert "Error parsing DAT: Parse Error" in report.text


def test_worker_identify_all_no_dats(tmp_path, mock_logger, mock_args):
    """Test identify_all when no DATs directory is found."""
    mock_args.dats_roots = []

    report = worker_identify_all(tmp_path, mock_args, mock_logger, lambda p: [])

    assert "Error: DATs directory not found" in report.text


def test_worker_identify_all_success(tmp_path, mock_logger, mock_args):
    """Test successful identification flow."""
    dats_root = tmp_path / "dats"
    dats_root.mkdir()
    (dats_root / "snes.dat").touch()
    mock_args.dats_roots = [dats_root]

    # Mock dependencies
    with (
        patch("emumanager.workers.verification.dat_parser.DatDb"),
        patch(
            "emumanager.workers.verification.dat_parser.parse_dat_file"
        ) as mock_parse,
        patch("emumanager.workers.verification._run_verification") as mock_run,
    ):
        mock_run.return_value = VerifyReport(text="Success")

        worker_identify_all(tmp_path, mock_args, mock_logger, lambda p: [])

        # Should parse found DATs
        assert mock_parse.call_count >= 1
        # Should run verification
        mock_run.assert_called()
