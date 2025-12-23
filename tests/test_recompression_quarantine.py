import importlib


from tests.helpers import Args


def test_handle_compression_replacement(monkeypatch, tmp_path):
    # Setup a fake file and environment
    fp = tmp_path / "game.nsz"
    fp.write_text("data")

    so = importlib.import_module("switch_organizer")
    # configure args to force recompress path
    so.args = Args(compress=True, recompress=True, dry_run=False, level=19)
    so.TOOL_NSZ = "nsz"
    so.ROMS_DIR = tmp_path

    # Monkeypatch compression helpers
    comp_mod = importlib.import_module("emumanager.switch.compression")

    produced = [tmp_path / "new.nsz"]

    def fake_try_multiple(tmpdir, attempts, run_cmd, **kwargs):
        return produced

    def fake_handle(produced_p, original, run_cmd, verify_fn, args, roms_dir):
        # simulate successful replace of original
        assert original == fp
        return original

    monkeypatch.setattr(comp_mod, "try_multiple_recompress_attempts", fake_try_multiple)
    monkeypatch.setattr(comp_mod, "handle_produced_file", fake_handle)

    res = so.handle_compression(fp)
    assert res == fp


def test_handle_compression_returns_candidate(monkeypatch, tmp_path):
    fp = tmp_path / "game.nsz"
    fp.write_text("data")

    so = importlib.import_module("switch_organizer")
    so.args = Args(compress=True, recompress=True, dry_run=False, level=19)
    so.TOOL_NSZ = "nsz"
    so.ROMS_DIR = tmp_path

    comp_mod = importlib.import_module("emumanager.switch.compression")

    produced = [tmp_path / "candidate.nsz"]

    def fake_try_multiple(tmpdir, attempts, run_cmd, **kwargs):
        return produced

    def fake_handle(produced_p, original, run_cmd, verify_fn, args, roms_dir):
        # return a candidate path (not replacing original)
        return produced_p

    monkeypatch.setattr(comp_mod, "try_multiple_recompress_attempts", fake_try_multiple)
    monkeypatch.setattr(comp_mod, "handle_produced_file", fake_handle)

    res = so.handle_compression(fp)
    assert res == produced[0]


def test_handle_compression_handle_raises(monkeypatch, tmp_path):
    fp = tmp_path / "game.nsz"
    fp.write_text("data")

    so = importlib.import_module("switch_organizer")
    so.args = Args(compress=True, recompress=True, dry_run=False, level=19)
    so.TOOL_NSZ = "nsz"
    so.ROMS_DIR = tmp_path

    comp_mod = importlib.import_module("emumanager.switch.compression")

    produced = [tmp_path / "candidate.nsz"]

    def fake_try_multiple(tmpdir, attempts, run_cmd, **kwargs):
        return produced

    def fake_handle(produced_p, original, run_cmd, verify_fn, args, roms_dir):
        raise RuntimeError("simulated failure in handle_produced_file")

    monkeypatch.setattr(comp_mod, "try_multiple_recompress_attempts", fake_try_multiple)
    monkeypatch.setattr(comp_mod, "handle_produced_file", fake_handle)

    # if handler raises, handle_compression should catch and return original
    res = so.handle_compression(fp)
    assert res == fp


def test_handle_compression_dry_run_skips_recompress(monkeypatch, tmp_path):
    fp = tmp_path / "game.nsz"
    fp.write_text("data")

    so = importlib.import_module("switch_organizer")
    # dry_run should short-circuit recompression
    so.args = Args(compress=True, recompress=True, dry_run=True, level=19)
    so.TOOL_NSZ = "nsz"
    so.ROMS_DIR = tmp_path

    comp_mod = importlib.import_module("emumanager.switch.compression")

    def should_not_be_called(*a, **k):
        raise AssertionError("recompress helper was called during dry_run")

    monkeypatch.setattr(comp_mod, "try_multiple_recompress_attempts", should_not_be_called)
    monkeypatch.setattr(comp_mod, "handle_produced_file", should_not_be_called)

    res = so.handle_compression(fp)
    assert res == fp
