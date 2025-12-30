from pathlib import Path

from emumanager.workers.ps2 import _strip_serial_tokens


def test_strip_serial_tokens_tmp(tmp_path: Path):
    # Create a fake Path-like object using pathlib.Path for its name/stem
    class Dummy:
        def __init__(self, name):
            self.name = name
            self._path = tmp_path / name

        @property
        def stem(self):
            return Path(self.name).stem

        @property
        def suffix(self):
            return Path(self.name).suffix

        @property
        def parent(self):
            return tmp_path

    # Calling _organize_ps2_file directly requires many params; we emulate
    # the minimal behavior needed to exercise the stripping logic.

    # Test that _strip_serial_tokens removes multiple bracketed serials
    stem = "Game Title [SLUS-20946] [SLUS20946]"
    cleaned = _strip_serial_tokens(stem)
    assert "[SLUS" not in cleaned
    assert cleaned.startswith("Game Title")
