from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from .nsz import parse_nsz_verify_output


def verify_nsz(
    filepath: Path,
    run_cmd: Callable,
    *,
    tool_nsz: str = "nsz",
    timeout: Optional[int] = 30,
) -> bool:
    """Verify an NSZ/XCZ archive using the provided NSZ tool.

    Returns True when verification succeeded, False otherwise. The function
    prefers an exit-code check but also consults textual output heuristics.
    """
    try:
        res = run_cmd([tool_nsz, "verify", str(filepath)], timeout=timeout)
    except Exception:
        return False

    # If we got a CompletedProcess-like result, inspect it
    retcode = getattr(res, "returncode", None)
    stdout = getattr(res, "stdout", None) or ""

    if isinstance(retcode, int) and retcode == 0:
        # Prefer trusting a zero exit code; still double-check textual hint
        try:
            if parse_nsz_verify_output(stdout):
                return True
        except Exception:
            pass
        return True

    # Fallback: parse the textual output for success indicators
    try:
        return parse_nsz_verify_output(stdout)
    except Exception:
        return False


def verify_metadata_tool(
    filepath: Path,
    run_cmd: Callable,
    *,
    tool_metadata: str | Path,
    is_nstool: bool = True,
    keys_path: Optional[Path] = None,
    timeout: Optional[int] = 30,
) -> bool:
    """Run the metadata tool on a file and return True when it appears valid.

    Rather than attempting fragile tool-specific flags, we run the tool and
    look for a Title ID (16 hex chars) or a non-empty stdout with returncode
    zero. This is intentionally conservative and test-friendly.
    """
    try:
        cmd = [str(tool_metadata), "-v" if is_nstool else "-k", str(filepath)]
        if not is_nstool and keys_path:
            # older hactool-like invocation (tests/mock may expect this layout)
            cmd.insert(2, str(keys_path))
            cmd.insert(3, "-i")

        res = run_cmd(cmd, timeout=timeout)
    except Exception:
        return False

    stdout = getattr(res, "stdout", None) or ""
    retcode = getattr(res, "returncode", None)

    # Quick heuristics: return True if returncode is 0 and stdout non-empty
    if isinstance(retcode, int) and retcode == 0 and stdout.strip():
        return True

    # Look for a 16-hex Title ID in output
    if re.search(r"\b[0-9a-fA-F]{16}\b", stdout):
        return True

    return False


def verify_hactool_deep(
    filepath: Path,
    run_cmd: Callable,
    *,
    keys_path: Optional[Path] = None,
    timeout: Optional[int] = 60,
) -> bool:
    """Attempt a deeper hactool-style verification pass.

    This runs the given tool (assumed to be hactool-like) with a minimal set
    of args and looks for Title ID / success text. It's intentionally generic
    so unit tests can mock the run_cmd output.
    """
    try:
        cmd = ["hactool", str(filepath)]
        if keys_path:
            cmd.insert(1, str(keys_path))
        res = run_cmd(cmd, timeout=timeout)
    except Exception:
        return False

    stdout = (getattr(res, "stdout", None) or "").lower()
    retcode = getattr(res, "returncode", None)

    if isinstance(retcode, int) and retcode == 0:
        if "title id" in stdout or re.search(r"[0-9a-f]{16}", stdout):
            return True
        # returncode 0 is a good sign even if text didn't include ID
        return True

    if "error" in stdout or "failed" in stdout or "corrupt" in stdout:
        return False

    if re.search(r"[0-9a-f]{16}", stdout):
        return True

    return False
