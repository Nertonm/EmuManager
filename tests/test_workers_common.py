from pathlib import Path

import emumanager.workers.common as wc
from emumanager.logging_cfg import set_correlation_id


def test_get_logger_for_gui_idempotent():
    calls = []

    def cb(msg: str):
        calls.append(msg)

    logger1 = wc.get_logger_for_gui(cb, name="test.logger")
    logger2 = wc.get_logger_for_gui(cb, name="test.logger")
    assert logger1 is logger2


def test_gui_log_handler_emit_and_callback(monkeypatch):
    msgs = []

    def cb(msg: str):
        msgs.append(msg)

    logger = wc.get_logger_for_gui(cb, name="emumanager.testgui")
    # emit an info and a warning and an error
    logger.info("hello %s", "world")
    logger.warning("warn %s", "you")
    logger.error("err %s", "oops")

    # messages should have been delivered to callback
    assert any("hello world" in m for m in msgs)
    assert any("WARN:" in m or "warn you" in m for m in msgs)
    assert any("ERROR:" in m or "err oops" in m for m in msgs)


def test_gui_logger_prefix_with_correlation():
    msgs = []

    def cb(msg: str):
        msgs.append(msg)

    set_correlation_id("CID123")
    g = wc.GuiLogger(cb)
    g.info("msg %s", "A")
    g.warning("msg %s", "B")
    g.error("msg %s", "C")
    g.exception("msg %s", "D")

    # Each message should include the correlation id prefix
    assert any(m.startswith("[CID123]") for m in msgs)


def test_calculate_file_hash_and_progress(tmp_path):
    p = tmp_path / "f.bin"
    data = b"abcd" * 1024
    p.write_bytes(data)
    calls = []

    def prog(v):
        calls.append(v)

    h = wc.calculate_file_hash(p, algo="md5", chunk_size=256, progress_cb=prog)
    # md5 of data should match manual calculation
    import hashlib

    expect = hashlib.md5(data).hexdigest()
    assert h == expect
    assert calls  # progress called at least once


def test_create_file_progress_cb_calls_main():
    main_calls = []

    def main_cb(val, text):
        main_calls.append((val, text))

    cb = wc.create_file_progress_cb(main_cb, 0.2, 0.5, "file.bin")
    assert cb is not None
    cb(0.5)
    assert main_calls and main_calls[0][0] == 0.2 + (0.5 * 0.5)


def test_find_target_dir(tmp_path):
    base = tmp_path / "base"
    d1 = base / "sub1"
    d1.mkdir(parents=True)
    # should find sub1
    found = wc.find_target_dir(base, ["sub1", "sub2"])
    assert found == d1
    # if base name matches
    other = tmp_path / "match"
    other.mkdir()
    found2 = wc.find_target_dir(other, ["match", "x"])
    assert found2 == other


def test_emit_verification_result_and_collector():
    results = []

    def per_file(res):
        results.append(res)

    wc.emit_verification_result(
        per_file,
        filename=Path("rom.iso"),
        status="OK",
        title="Game",
        serial="S123",
        md5="m",
        sha1="s",
        crc="c",
    )
    assert results
    r = results[0]
    assert r.filename == "rom.iso"
    assert r.status == "OK"
    assert r.match_name == "Game [S123]"

    # test make_result_collector
    out = []

    def cb(x):
        out.append(x)

    collector = wc.make_result_collector(cb, out)
    collector(1)
    assert out and out[0] == 1


def test_skip_if_compressed_with_fake_db(tmp_path):
    class FakeEntry:
        def __init__(self):
            self.status = "COMPRESSED"

    class FakeDB:
        def __init__(self):
            self.logged = False

        def get_entry(self, path):
            return FakeEntry()

        def log_action(self, path, code, msg):
            self.logged = True

    msgs = []

    def log_cb(m: str):
        msgs.append(m)

    gui_logger = wc.GuiLogger(log_cb)
    f = tmp_path / "rom.iso"
    f.write_text("x")
    db = FakeDB()
    res = wc.skip_if_compressed(f, gui_logger, db=db)
    assert res is True
    assert db.logged is True
