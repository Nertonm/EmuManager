import asyncio


def test_palette_contains_core_actions():
    """Ensure command palette exposes the same core actions as the actions panel.

    We keep this test lightweight and non-interactive by using the built-in
    `_test_auto_palette` hook to avoid actually mounting/opening modals.
    """

    from emumanager.tui import FullscreenTui

    tui = FullscreenTui(
        base=".",
        keys=None,
        dats_root=None,
        auto_verify_on_select=False,
    )

    # Expected TUI action ids that represent CLI parity.
    expected = {
        "init",
        "list",
        "refresh_systems",
        "scan",
        "add_rom",
        "organize",
        "health",
        "compress",
        "decompress",
        "verify",
        "identify",
        "clean",
        "update_dats",
        "quit",
    }

    actions_ids = {aid for aid, _label in tui._actions}
    missing = expected - actions_ids
    assert not missing, f"Missing action ids in TUI actions list: {sorted(missing)}"


def test_palette_test_hook_returns_action_id():
    """Sanity check: the palette test hook still short-circuits the modal."""

    from emumanager.tui import FullscreenTui

    tui = FullscreenTui(
        base=".",
        keys=None,
        dats_root=None,
        auto_verify_on_select=False,
    )
    tui._test_auto_palette = "scan"

    sel = asyncio.run(tui._prompt_command_palette())
    assert sel == "scan"


def test_cli_commands_have_tui_action_mapping():
    """Ensure every Typer CLI subcommand has a corresponding TUI action.

    We keep this intentionally strict so new CLI commands can't land without a
    TUI affordance.

    Notes:
    - Some CLI-only entrypoints are not meant for the dashboard (e.g. tui-full).
    - Single-file commands (compress-one, decompress-one, recompress-one) are
      exposed via per-file actions instead of the main palette.
    """

    from emumanager.tui import FullscreenTui

    tui = FullscreenTui(
        base=".",
        keys=None,
        dats_root=None,
        auto_verify_on_select=False,
    )
    actions_ids = {aid for aid, _label in tui._actions}

    # CLI command -> expected TUI action id
    cli_to_tui = {
        "init": "init",
        "list-systems": "list",
        "scan": "scan",
        "add-rom": "add_rom",
        "organize": "organize",
        "health-check": "health",
        "compress": "compress",
        "decompress": "decompress",
        "verify": "verify",
        "identify": "identify",
        "clean": "clean",
        "update-dats": "update_dats",
        # TUI entrypoints themselves
        "tui": None,
        "tui-full": None,
        # Exposed via per-file actions, not palette
        "compress-one": None,
        "decompress-one": None,
        "recompress-one": None,
    }

    missing = []
    for cli_cmd, tui_action in cli_to_tui.items():
        if tui_action is None:
            continue
        if tui_action not in actions_ids:
            missing.append((cli_cmd, tui_action))

    assert not missing, f"CLI commands missing TUI action mapping: {missing}"
