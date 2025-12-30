from pathlib import Path

from emumanager.workers.psp import worker_psp_compress


class DummyArgs:
    rm_originals = False
    level = 9
    dry_run = False


def test_worker_psp_compress_multiple_files(tmp_path, monkeypatch):
    # Setup directory structure expected by worker: base/roms/psp
    base = tmp_path
    psp_dir = base / "roms" / "psp"
    psp_dir.mkdir(parents=True)

    good = psp_dir / "good.iso"
    fail = psp_dir / "fail.iso"
    skip = psp_dir / "skip.iso"

    good.write_bytes(b"good")
    fail.write_bytes(b"bad")
    skip.write_bytes(b"skip")

    # Pre-create skip.cso so the worker should skip compressing skip.iso
    skip.with_suffix(".cso").write_bytes(b"already")

    called_paths = []

    def fake_compress_to_cso(input_path, output_path, level=9, dry_run=False):
        called_paths.append(Path(input_path).name)
        if Path(input_path).name == "good.iso":
            output_path.write_bytes(b"cso")
            return True
        elif Path(input_path).name == "fail.iso":
            return False
        else:
            # Should not be called for skip.iso because CSO exists
            raise AssertionError("compress_to_cso should not be called for skip.iso")

    monkeypatch.setattr(
        "emumanager.workers.psp.psp_converter.compress_to_cso", fake_compress_to_cso
    )

    logs = []

    # list_files_fn returns files found in the PSP dir
    def list_files_fn(d):
        return [good, fail, skip]

    res = worker_psp_compress(
        base, DummyArgs(), lambda m: logs.append(m), list_files_fn
    )

    # Expect 1 success (good), 1 failed (fail), 1 skipped (skip)
    assert "Success: 1" in res
    assert "Failed: 1" in res
    assert "Skipped: 1" in res

    # Ensure compressor was called for good and fail only
    assert "good.iso" in called_paths
    assert "fail.iso" in called_paths
    assert "skip.iso" not in called_paths

    # Some log messages should exist
    assert any("Compressed" in m or "Skipping" in m or "Failed" in m for m in logs)
