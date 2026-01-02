import asyncio
import pytest

textual = pytest.importorskip("textual")

from emumanager.tui import FullscreenTui


def test_modal_select_level(tmp_path):
    import asyncio
    import pytest

    textual = pytest.importorskip("textual")

    from emumanager.tui import FullscreenTui


    def test_modal_select_level(tmp_path):
        async def run_case():
            # Setup a dummy file
            base = tmp_path
            roms = base / "roms" / "switch"
            roms.mkdir(parents=True)
            f = roms / "game.nsp"
            f.write_text("x")

            tui = FullscreenTui(
                base, None, None, auto_verify_on_select=False, assume_yes=True
            )
            # prevent noisy logs
            tui._log = lambda msg: None

            async with tui.run_test() as pilot:
                # start the prompt in background
                coro = tui._prompt_action_options(f, "compress")
                task = asyncio.create_task(coro)

                # Give the app a brief moment to mount the modal
                await pilot.pause(0.05)

                # Ensure modal mounted: look for the modal by id
                modal_found = False
                try:
                    # query_one may raise if not found
                    modal = tui.query_one("#modal_opts")
                    modal_found = modal is not None
                except Exception:
                    modal_found = False

                assert modal_found, "Modal did not mount"

                # Programmatically resolve selection (stable across textual versions)
                if getattr(tui, "_selection_future", None) is not None:
                    if not tui._selection_future.done():
                        try:
                            tui.call_from_thread(
                                tui._selection_future.set_result, "lvl_3"
                            )
                        except Exception:
                            tui._selection_future.set_result("lvl_3")

                result = await asyncio.wait_for(task, timeout=1.0)

                assert isinstance(result, dict)
                assert result.get("level") in (1, 3, 5, 9, 12, 18, 22)

        asyncio.run(run_case())
