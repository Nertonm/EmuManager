"""Script shim to launch the EmuManager GUI.

This preserves the old scripts-based workflow while the real implementation
lives under `emumanager.gui`.
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path so `from emumanager import ...` resolves to
# the package directory instead of accidentally importing a top-level module
# named `emumanager` from the scripts/ folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Ensure the project root is first on sys.path so the `emumanager` package
# directory is preferred over any same-named scripts/ module in this folder.
try:
    if str(PROJECT_ROOT) != sys.path[0]:
        # Remove any existing PROJECT_ROOT entry and place it first.
        if str(PROJECT_ROOT) in sys.path:
            sys.path.remove(str(PROJECT_ROOT))
        sys.path.insert(0, str(PROJECT_ROOT))
        # Also remove the scripts/ directory from sys.path if present to avoid
        # accidentally shadowing the package with a top-level module named
        # `emumanager` located under scripts/.
        script_dir = str(Path(__file__).resolve().parent)
        if script_dir in sys.path:
            try:
                sys.path.remove(script_dir)
            except Exception:
                pass
except Exception:
    # Best-effort only; importing may still work in many environments.
    pass

from emumanager.gui import main  # noqa: E402


def _headless_smoke_test() -> int:
    """Do a headless smoke test useful for CI or headless environments.

    It will call the manager API in dry-run mode on a temporary directory.
    """
    import tempfile
    from emumanager import manager

    tmp = Path(tempfile.mkdtemp(prefix="emumanager_smoke_"))
    print("Headless smoke test: init dry-run on", tmp)
    rc = manager.cmd_init(tmp, dry_run=True)
    print("Smoke test rc:", rc)
    return rc


def _main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if isinstance(argv, (list, tuple)):
        args = list(argv)
    else:
        args = [str(argv)]

    if "--headless" in args:
        return _headless_smoke_test()

    return main()


if __name__ == "__main__":
    raise SystemExit(_main())
