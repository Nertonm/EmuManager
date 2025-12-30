from pathlib import Path

from emumanager.workers.dolphin import worker_dolphin_convert_single


class DummyArgs:
    rm_originals = True


def test_worker_dolphin_convert_single_rm_originals_success(tmp_path, monkeypatch):
    iso = tmp_path / "game.iso"
    iso.write_bytes(b"data")

    rvz_path = iso.with_suffix(".rvz")

    class DummyConverter:
        def __init__(self, logger=None):
            pass

        def check_tool(self):
            return True

        def convert_to_rvz(self, input_file, output_file):
            # simulate successful conversion by creating the rvz file
            output_file.write_bytes(b"rvz")
            return True

    # Ensure safe_unlink actually removes files when called
    def fake_safe_unlink(path, logger):
        Path(path).unlink()

    monkeypatch.setattr("emumanager.workers.dolphin.DolphinConverter", DummyConverter)
    monkeypatch.setattr("emumanager.common.fileops.safe_unlink", fake_safe_unlink)

    logs = []
    res = worker_dolphin_convert_single(iso, DummyArgs(), lambda m: logs.append(m))

    assert "Converted: 1" in res
    assert rvz_path.exists()
    # original should have been removed
    assert not iso.exists()


def test_worker_dolphin_convert_single_rm_originals_failure(tmp_path, monkeypatch):
    iso = tmp_path / "game2.iso"
    iso.write_bytes(b"data")

    class DummyConverterFail:
        def __init__(self, logger=None):
            pass

        def check_tool(self):
            return True

        def convert_to_rvz(self, input_file, output_file):
            # Simulate a conversion failure
            return False

    # safe_unlink should not be called; provide a fake that would raise if called
    def fake_safe_unlink_raises(path, logger):
        raise AssertionError("safe_unlink should not be called on failure")

    monkeypatch.setattr(
        "emumanager.workers.dolphin.DolphinConverter", DummyConverterFail
    )
    monkeypatch.setattr(
        "emumanager.common.fileops.safe_unlink", fake_safe_unlink_raises
    )

    logs = []
    res = worker_dolphin_convert_single(iso, DummyArgs(), lambda m: logs.append(m))

    assert "Converted: 0" in res or "Converted: 1" not in res
    # original should still exist
    assert iso.exists()
