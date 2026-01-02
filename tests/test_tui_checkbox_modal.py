import asyncio
import pytest

textual = pytest.importorskip("textual")

from emumanager.tui import FullscreenTui


def test_checkbox_modal(tmp_path):
    async def run_case():
        # Setup a dummy file in a switch folder
        base = tmp_path
        roms = base / "roms" / "switch"
        roms.mkdir(parents=True)
        f = roms / "game.nsp"
        f.write_text("x")

        tui = FullscreenTui(
            base, None, None, auto_verify_on_select=False, assume_yes=True
        )
        # silence logs for the test
        tui._log = lambda msg: None

        # Use the test-only auto-options hook to avoid modal timing races.
        tui._test_auto_options = {"level": 3, "rm_originals": True, "dry_run": False}

        async with tui.run_test() as pilot:
            result = await tui._prompt_action_options(f, "compress")

        assert isinstance(result, dict)
        assert result.get("level") == 3
        assert result.get("rm_originals") is True
        assert result.get("dry_run") is False

    asyncio.run(run_case())
