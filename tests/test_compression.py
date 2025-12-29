from emumanager.switch.compression import (
    build_nsz_command,
    recompress_candidate,
    replace_if_verified,
)


class DummyRes:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_build_nsz_command(tmp_path):
    src = tmp_path / "in.nsp"
    dst = tmp_path / "out.nsz"
    cmd = build_nsz_command(src, dst, level=5, tool_nsz="nszbin")
    assert str(src) in cmd
    assert str(dst) in cmd
    assert "5" in cmd


def test_recompress_candidate_calls_run_cmd(tmp_path):
    src = tmp_path / "in.nsp"
    dst = tmp_path / "out.nsz"
    src.write_text("dummy")

    def run_cmd(cmd, *, timeout=None):
        # simulate a successful recompress
        return DummyRes(stdout="compressed", returncode=0)

    res = recompress_candidate(src, dst, run_cmd, level=7, tool_nsz="nszbin")
    assert getattr(res, "returncode", None) == 0


def test_replace_if_verified_replaces(tmp_path):
    dest = tmp_path / "games" / "game.nsz"
    tmpf = tmp_path / "tmp" / "candidate.nsz"
    tmpf.parent.mkdir()
    tmpf.write_text("data")

    def run_cmd(cmd, *, timeout=None):
        return DummyRes(stdout="ok", returncode=0)

    def verify_fn(path, run_cmd):
        # verify returns true for this test
        return True

    result = replace_if_verified(
        tmpf, dest, run_cmd, verify_fn=verify_fn, dry_run=False
    )
    assert result is True
    assert dest.exists()


def test_replace_if_verified_dry_run(tmp_path):
    dest = tmp_path / "games" / "game.nsz"
    tmpf = tmp_path / "tmp" / "candidate.nsz"
    tmpf.parent.mkdir()
    tmpf.write_text("data")

    def run_cmd(cmd, *, timeout=None):
        return DummyRes(stdout="ok", returncode=0)

    def verify_fn(path, run_cmd):
        return True

    result = replace_if_verified(tmpf, dest, run_cmd, verify_fn=verify_fn, dry_run=True)
    assert result is True
    assert not dest.exists()


def test_try_multiple_recompress_attempts(tmp_path):
    # create a tmpdir and a dummy produced file
    work = tmp_path / "work"
    work.mkdir()
    produced = work / "game.nsz"
    produced.write_text("data")

    def run_cmd(cmd, *, timeout=None):
        # pretend the tool ran; do nothing
        return DummyRes(stdout="", returncode=0)

    from emumanager.switch.compression import try_multiple_recompress_attempts

    attempts = [["nsz", "-C", "-l", "3", "in.nsp"]]
    found = try_multiple_recompress_attempts(work, attempts, run_cmd)
    assert any(p.name == "game.nsz" for p in found)


def test_handle_produced_file_success(tmp_path):
    roms_dir = tmp_path / "roms"
    roms_dir.mkdir()
    original = roms_dir / "game.nsz"
    original.write_text("old")
    produced = tmp_path / "prod" / "game.nsz"
    produced.parent.mkdir()
    produced.write_text("new")

    def run_cmd(cmd, *, timeout=None):
        return DummyRes(stdout="", returncode=0)

    def verify_fn(path, run_cmd):
        return True

    from emumanager.switch.compression import handle_produced_file

    result = handle_produced_file(
        produced,
        original,
        run_cmd,
        verify_fn,
        args=type("A", (), {"keep_on_failure": False, "dry_run": False}),
        roms_dir=roms_dir,
    )
    assert result == original
    assert original.exists()


def test_compress_file_returns_candidate(tmp_path):
    src = tmp_path / "game.nsp"
    src.write_text("data")
    # create a compressed candidate expected
    out = tmp_path / "game.nsz"
    out.write_text("comp")

    def run_cmd(cmd, *, filebase=None, timeout=None, check=False):
        # simulate successful compression (tool produced the file)
        return DummyRes(stdout="", returncode=0)

    from emumanager.switch.compression import compress_file

    cand = compress_file(
        src,
        run_cmd,
        tool_nsz="nsz",
        level=3,
        args=type("A", (), {"cmd_timeout": None}),
        roms_dir=tmp_path,
    )
    assert cand is not None
    assert cand.name.endswith(".nsz")


def test_decompress_and_find_candidate(tmp_path):
    # create compressed file and decompressed candidate
    comp = tmp_path / "game.nsz"
    comp.write_text("data")
    cand = tmp_path / "game.nsp"
    cand.write_text("inner")
    # set mtimes
    import os

    os.utime(comp, None)
    os.utime(cand, None)

    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="", returncode=0)

    from emumanager.switch.compression import decompress_and_find_candidate

    found = decompress_and_find_candidate(
        comp,
        run_cmd,
        tool_nsz="nsz",
        tool_metadata=None,
        is_nstool=True,
        keys_path=None,
        args=type(
            "A",
            (),
            {"cmd_timeout": None, "dry_run": False, "keep_on_failure": False},
        ),
        roms_dir=tmp_path,
    )
    assert found is not None
    assert found.exists()
