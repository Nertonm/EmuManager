import types

import emumanager.switch.cli as so


class A:
    pass


def setup_args(a, **kwargs):
    a.compress = False
    a.recompress = False
    a.rm_originals = False
    a.dry_run = False
    a.level = 3
    for k, v in kwargs.items():
        setattr(a, k, v)
    return a


# Dummy TemporaryDirectory context manager used to control where nsz writes output
class DummyTemp:
    def __init__(self, target_dir):
        self.name = str(target_dir)

    def __enter__(self):
        return self.name

    def __exit__(self, exc_type, exc, tb):
        return False


def test_recompress_explicit(monkeypatch, tmp_path):
    # Create a fake .nsz file
    src = tmp_path / "SomeGame [0100ABCDEF000030].nsz"
    src.write_bytes(b"oldcompressed")

    tool_nsz = tmp_path / "nsz"
    so.args = setup_args(A(), compress=True, recompress=True, dry_run=False, level=19)

    # prepare a tmpdir for nsz to write its output
    prod_dir = tmp_path / "recomp_out"
    prod_dir.mkdir()

    # Monkeypatch TemporaryDirectory to yield our prod_dir
    monkeypatch.setattr(
        so.tempfile,
        "TemporaryDirectory",
        lambda prefix=None: DummyTemp(prod_dir),
    )

    # Fake subprocess.run: when called with nsz -C create a new .nsz inside prod_dir
    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(map(str, cmd))
        if str(tool_nsz) in cmd_str and "-C" in cmd_str:
            out_file = prod_dir / (src.stem + "_recomp.nsz")
            out_file.write_bytes(b"newcompressed")
            return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(so.subprocess, "run", fake_run)
    # ensure verification passes
    monkeypatch.setattr(so, "verify_integrity", lambda f, **k: True)
    # make detect_nsz_level return lower than target so recompress is triggered
    monkeypatch.setattr(so, "detect_nsz_level", lambda f, **k: 1)

    res = so.handle_compression(
        src,
        args=so.args,
        tool_nsz=tool_nsz,
        roms_dir=tmp_path,
        tool_metadata=None,
        is_nstool=False,
        keys_path=None,
        cmd_timeout=None,
        tool_hactool=None,
    )
    # After successful recompress replacement the function returns the filepath
    assert res == src
    assert src.exists()


def test_recompress_verify_fail(monkeypatch, tmp_path):
    src = tmp_path / "FailGame [0100ABCDEF000031].nsz"
    src.write_bytes(b"oldcompressed2")

    tool_nsz = tmp_path / "nsz"
    so.args = setup_args(A(), compress=True, recompress=True, dry_run=False, level=19)

    prod_dir = tmp_path / "recomp_out2"
    prod_dir.mkdir()
    monkeypatch.setattr(
        so.tempfile,
        "TemporaryDirectory",
        lambda prefix=None: DummyTemp(prod_dir),
    )

    def fake_run(cmd, **kwargs):
        if str(tool_nsz) in " ".join(map(str, cmd)) and "-C" in cmd:
            out_file = prod_dir / (src.stem + "_recomp.nsz")
            out_file.write_bytes(b"new")
            return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        return types.SimpleNamespace(returncode=1, stdout="", stderr="err")

    monkeypatch.setattr(so.subprocess, "run", fake_run)
    monkeypatch.setattr(so, "verify_integrity", lambda f, **k: False)
    monkeypatch.setattr(so, "detect_nsz_level", lambda f, **k: 1)

    res = so.handle_compression(
        src,
        args=so.args,
        tool_nsz=tool_nsz,
        roms_dir=tmp_path,
        tool_metadata=None,
        is_nstool=False,
        keys_path=None,
        cmd_timeout=None,
        tool_hactool=None,
    )
    # When verification fails, original should remain
    assert src.exists()
    assert res == src


def test_recompress_dry_run(monkeypatch, tmp_path):
    src = tmp_path / "Dry [0100ABCDEF000032].nsz"
    src.write_bytes(b"old")

    tool_nsz = tmp_path / "nsz"
    so.args = setup_args(A(), compress=True, recompress=True, dry_run=True, level=19)

    # If dry-run, subprocess.run should not be called; we'll set a fake that raises
    def fake_run(cmd, **kwargs):
        raise RuntimeError("should not call nsz in dry-run")

    monkeypatch.setattr(so.subprocess, "run", fake_run)
    monkeypatch.setattr(so, "detect_nsz_level", lambda f, **k: 1)

    res = so.handle_compression(
        src,
        args=so.args,
        tool_nsz=tool_nsz,
        roms_dir=tmp_path,
        tool_metadata=None,
        is_nstool=False,
        keys_path=None,
        cmd_timeout=None,
        tool_hactool=None,
    )
    assert res == src
    assert src.exists()
