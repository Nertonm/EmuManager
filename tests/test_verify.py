from pathlib import Path

from emumanager.switch.verify import (
    verify_hactool_deep,
    verify_metadata_tool,
    verify_nsz,
)


class DummyRes:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_verify_nsz_success():
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="Verification: OK", returncode=0)

    assert verify_nsz(Path("/tmp/test.nsz"), run_cmd, tool_nsz="nsz") is True


def test_verify_nsz_failure():
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="Error: corrupt archive", returncode=2)

    assert verify_nsz(Path("/tmp/test.nsz"), run_cmd, tool_nsz="nsz") is False


def test_verify_metadata_tool_success():
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="Name: Foo\nTitle ID: 0100ABCDEF000011", returncode=0)

    assert verify_metadata_tool(
        Path("/tmp/test.nsp"),
        run_cmd,
        tool_metadata="/usr/bin/nstool",
        is_nstool=True,
    )


def test_verify_metadata_tool_failure():
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="", returncode=1)

    assert (
        verify_metadata_tool(
            Path("/tmp/test.nsp"),
            run_cmd,
            tool_metadata="/usr/bin/nstool",
            is_nstool=True,
        )
        is False
    )


def test_verify_hactool_deep_success():
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(
            stdout="Some output... Title ID: 0100ABCDEF000012", returncode=0
        )

    assert verify_hactool_deep(Path("/tmp/game.nsp"), run_cmd, keys_path=None) is True


def test_verify_hactool_deep_failure():
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="ERROR: failed to parse", returncode=1)

    assert verify_hactool_deep(Path("/tmp/game.nsp"), run_cmd, keys_path=None) is False
