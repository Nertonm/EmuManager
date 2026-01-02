from types import SimpleNamespace

from emumanager.tui import FullscreenTui


def make_verify_result(
    filename,
    full_path,
    status="VERIFIED",
    match_name="Game",
    dat_name="test.dat",
):
    return SimpleNamespace(
        filename=filename,
        full_path=full_path,
        status=status,
        match_name=match_name,
        dat_name=dat_name,
    )


def test_per_file_verify_filters(tmp_path, monkeypatch):
    # Setup a fake file and a fake report containing multiple results
    base = tmp_path
    system_dir = base / "roms" / "snes"
    system_dir.mkdir(parents=True)
    target_file = system_dir / "super.nes"
    target_file.write_text("dummy")

    # Fake report with two entries, one matching our target
    r1 = make_verify_result(
        "other.nes", str(system_dir / "other.nes"), status="MISMATCH"
    )
    r2 = make_verify_result("super.nes", str(target_file), status="VERIFIED")
    fake_report = SimpleNamespace(results=[r1, r2], text="Summary")

    # Patch worker_hash_verify to return our fake report
    monkeypatch.setattr(
        "emumanager.tui.worker_hash_verify",
        lambda base_path, args, log_cb, list_fn: fake_report,
    )
    # Patch _switch_env to avoid external tooling
    monkeypatch.setattr("emumanager.tui._switch_env", lambda a, b, c: {})

    logs = []

    tui = FullscreenTui(base, None, None, auto_verify_on_select=False, assume_yes=True)
    # avoid Textual internals by capturing log messages
    tui._log = lambda msg: logs.append(msg)

    # Run per-file verify
    tui._run_file_action_sync(target_file, "verify", options=None)

    # Ensure logs contain the single-file report line
    joined = "\n".join(logs)
    assert "File: " in joined
    assert "super.nes" in joined
    assert "VERIFIED" in joined or "VERIFIED" == r2.status


def test_compress_options_passed(tmp_path, monkeypatch):
    base = tmp_path
    system_dir = base / "roms" / "switch"
    system_dir.mkdir(parents=True)
    target_file = system_dir / "game.nsp"
    target_file.write_text("dummy")

    captured = {}

    def fake_compress(filepath, env, args, log_cb):
        # capture args passed to the worker
        captured["level"] = getattr(args, "level", None)
        captured["rm_originals"] = getattr(args, "rm_originals", None)
        captured["dry_run"] = getattr(args, "dry_run", None)
        log_cb("compressed")
        return "OK"

    monkeypatch.setattr("emumanager.tui.worker_compress_single", fake_compress)
    monkeypatch.setattr("emumanager.tui._switch_env", lambda a, b, c: {})

    logs = []
    tui = FullscreenTui(base, None, None, auto_verify_on_select=False, assume_yes=True)
    tui._log = lambda msg: logs.append(msg)

    opts = {"level": 9, "rm_originals": True, "dry_run": False}
    tui._run_file_action_sync(target_file, "compress", options=opts)

    assert captured.get("level") == 9
    assert captured.get("rm_originals") is True
    assert captured.get("dry_run") is False
