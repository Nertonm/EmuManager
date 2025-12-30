import os

from emumanager.workers import verification


class DummyDB:
    def lookup(self, crc=None, md5=None, sha1=None):
        return []


def test_hash_failure_sets_status_and_logs(tmp_path, caplog):
    # Create a file and remove read permissions to simulate hash failure
    f = tmp_path / "failme.iso"
    f.write_bytes(b"abc")
    os.chmod(f, 0)  # Remove all permissions

    # Provide a logger so the failure message is captured
    class Logger:
        def __init__(self):
            self.warnings = []

        def warning(self, msg):
            self.warnings.append(msg)

    logger = Logger()
    args = type("Args", (), {"logger": logger, "system_name": "test"})()
    res = verification._verify_single_file(f, DummyDB(), args, None, 0, 1, None)

    # Restore permissions for cleanup
    os.chmod(f, 0o644)

    assert res.status == "HASH_FAILED"
    assert res.match_name and "HASH_FAILED" in res.match_name
    assert res.crc is None and res.sha1 is None and res.md5 is None

    # Should log a warning if logger is present
    assert any("Hash calculation failed" in w for w in logger.warnings)
