from emumanager.workers.dolphin import worker_dolphin_convert_single


class DummyArgs:
    rm_originals = False


def test_worker_dolphin_convert_single_monkeypatched(tmp_path, monkeypatch):
    # Create a dummy iso file
    iso = tmp_path / "test_game.iso"
    iso.write_bytes(b"dummy")

    # Monkeypatch DolphinConverter to avoid calling external tool
    class DummyConverter:
        def __init__(self, logger=None):
            pass

        def check_tool(self):
            return True

        def convert_to_rvz(self, input_file, output_file):
            # Simulate successful conversion by creating the output file
            output_file.write_bytes(b"rvz")
            return True

    monkeypatch.setattr("emumanager.workers.dolphin.DolphinConverter", DummyConverter)

    # Run worker
    res = worker_dolphin_convert_single(iso, DummyArgs(), lambda m: None)

    assert isinstance(res, str)
    assert "Converted: 1" in res
    # Ensure rvz file was created
    assert (iso.with_suffix(".rvz")).exists()
