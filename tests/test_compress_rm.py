import types

import switch_organizer as so


class A:
    pass


def setup_args(args_obj, compress=True, rm_originals=False, dry_run=False, level=1):
    args_obj.compress = compress
    args_obj.rm_originals = rm_originals
    args_obj.dry_run = dry_run
    args_obj.level = level
    args_obj.decompress = False
    args_obj.dup_check = "fast"
    return args_obj


def test_rm_originals_success(monkeypatch, tmp_path):
    src = tmp_path / "Game Title [0100ABCDEF000010].nsp"
    src.write_bytes(b"original")
    compressed = tmp_path / "Game Title [0100ABCDEF000010].nsz"

    so.TOOL_NSZ = tmp_path / "nsz"
    so.args = setup_args(A(), compress=True, rm_originals=True, dry_run=False)

    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(map(str, cmd))
        # simulate nsz compression producing an .nsz file
        if str(so.TOOL_NSZ) in cmd_str and "-C" in cmd_str:
            compressed.write_bytes(b"compressed")
            return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(so.subprocess, "run", fake_run)
    monkeypatch.setattr(so, "verify_integrity", lambda f, deep=False: True)

    result = so.handle_compression(src)

    assert not src.exists(), "Original should be removed after successful compression"
    assert compressed.exists(), "Compressed file must exist"
    assert result == compressed


def test_rm_originals_keep_on_verify_fail(monkeypatch, tmp_path):
    src = tmp_path / "AnotherGame [0100ABCDEF000011].nsp"
    src.write_bytes(b"original2")
    compressed = tmp_path / "AnotherGame [0100ABCDEF000011].nsz"

    so.TOOL_NSZ = tmp_path / "nsz"
    so.args = setup_args(A(), compress=True, rm_originals=True, dry_run=False)

    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(map(str, cmd))
        if str(so.TOOL_NSZ) in cmd_str and "-C" in cmd_str:
            compressed.write_bytes(b"compressed2")
            return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(so.subprocess, "run", fake_run)
    # simulate integrity failure on compressed file
    monkeypatch.setattr(so, "verify_integrity", lambda f, deep=False: False)

    result = so.handle_compression(src)

    assert src.exists(), "Original must be kept if compressed file fails verification"
    assert compressed.exists(), "Compressed file should still be present"
    assert result == compressed


def test_rm_originals_compress_fails(monkeypatch, tmp_path):
    src = tmp_path / "FailGame [0100ABCDEF000012].nsp"
    src.write_bytes(b"orig3")

    so.TOOL_NSZ = tmp_path / "nsz"
    so.args = setup_args(A(), compress=True, rm_originals=True, dry_run=False)

    def fake_run_fail(cmd, **kwargs):
        # simulate compression tool failure by raising
        raise RuntimeError("compression failed")

    monkeypatch.setattr(so.subprocess, "run", fake_run_fail)

    result = so.handle_compression(src)

    # When compression raises, handle_compression returns original filepath unchanged
    assert src.exists(), "Original must remain when compression fails"
    assert result == src


def test_rm_originals_dry_run(monkeypatch, tmp_path):
    src = tmp_path / "DryRunGame [0100ABCDEF000013].nsp"
    src.write_bytes(b"orig4")

    so.TOOL_NSZ = tmp_path / "nsz"
    so.args = setup_args(A(), compress=True, rm_originals=True, dry_run=True)

    # Should not attempt to run subprocess; but if it does, simulate creation
    def fake_run(cmd, **kwargs):
        raise RuntimeError("should not be called in dry-run")

    monkeypatch.setattr(so.subprocess, "run", fake_run)

    result = so.handle_compression(src)

    assert src.exists(), "Dry-run must not remove original"
    assert result.suffix == ".nsz" or result == src.with_suffix(".nsz"), (
        "In dry-run, function returns target .nsz path"
    )
