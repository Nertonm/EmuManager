from emumanager.workers.psp import worker_psp_compress_single


class DummyArgs:
    rm_originals = False
    level = 9
    dry_run = False


def test_worker_psp_compress_single_monkeypatched(tmp_path, monkeypatch):
    # Create dummy iso
    iso = tmp_path / "game.iso"
    iso.write_bytes(b"data")

    created = {"flag": False}

    def fake_compress_to_cso(input_path, output_path, level=9, dry_run=False):
        # simulate successful compression by creating the cso file
        output_path.write_bytes(b"cso")
        created["flag"] = True
        return True

    # Patch the converter used inside the worker module
    monkeypatch.setattr(
        "emumanager.workers.psp.psp_converter.compress_to_cso", fake_compress_to_cso
    )

    logs = []
    res = worker_psp_compress_single(iso, DummyArgs(), lambda m: logs.append(m))

    assert "Success: 1" in res
    assert created["flag"] is True
    assert (iso.with_suffix(".cso")).exists()
    assert any("Compressed" in m or "Skipping" in m or "Failed" in m for m in logs)
