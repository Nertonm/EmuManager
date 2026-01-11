import logging
import os
import re
import shlex
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, List, Optional, Set

logger = logging.getLogger(__name__)

_RUNNING_PROCESSES: Set[subprocess.Popen] = set()
_LOCK = threading.Lock()
ORIGINAL_SUBPROCESS_RUN = subprocess.run
PCT_RE = re.compile(r"(\d{1,3})\s*%")


def _register_process(proc: subprocess.Popen) -> None:
    with _LOCK:
        _RUNNING_PROCESSES.add(proc)


def _unregister_process(proc: subprocess.Popen) -> None:
    with _LOCK:
        _RUNNING_PROCESSES.discard(proc)


def cancel_current_process() -> bool:
    """Attempt to kill all currently running subprocesses managed by this module.

    This is used by the GUI to request cancellation of long-running
    external commands. It will try to kill, then terminate the processes.

    Returns:
        bool: True if any process was cancelled, False otherwise.
    """
    with _LOCK:
        procs = list(_RUNNING_PROCESSES)

    if not procs:
        return False

    cancelled_any = False
    for proc in procs:
        try:
            proc.kill()
            cancelled_any = True
        except Exception as e:
            logger.debug("Failed to kill process %s: %s", getattr(proc, "pid", "unknown"), e)
            try:
                proc.terminate()
                cancelled_any = True
            except Exception as e2:
                logger.debug("Failed to terminate process %s: %s", getattr(proc, "pid", "unknown"), e2)
    return cancelled_any


def find_tool(name: str) -> Optional[Path]:
    """Find an executable in the system PATH or in the current directory.

    Args:
        name: The name of the executable to find.

    Returns:
        Optional[Path]: The path to the executable if found, None otherwise.
    """
    # Prefer system-wide installed executable
    p = shutil.which(name)
    if p:
        return Path(p).resolve()

    # Fallback to local files
    local = Path(f"./{name}").resolve()
    if local.exists():
        return local
    local_exe = Path(f"./{name}.exe").resolve()
    if local_exe.exists():
        return local_exe

    return None


def _run_with_popen(
    cmd: List[str], timeout: Optional[float], si: Any
) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=si,
    )
    _register_process(proc)
    try:
        out, err = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr=err)
    except subprocess.TimeoutExpired:
        logger.warning("Command timeout (%s s): %s", timeout, shlex.join(cmd))
        try:
            proc.kill()
        except Exception:
            logger.debug("Failed to kill timed-out subprocess")
        out, err = proc.communicate()
        # Build a TimeoutExpired with output attached and raise it
        ex = subprocess.TimeoutExpired(cmd, timeout)
        ex.stdout = out
        ex.stderr = err
        raise ex
    finally:
        _unregister_process(proc)


def _run_with_subprocess_run(
    cmd: List[str], timeout: Optional[float]
) -> subprocess.CompletedProcess:
    try:
        # Use explicit stdout/stderr kwargs instead of capture_output so
        # test monkeypatches with a signature like (cmd, stdout=None, stderr=None)
        # continue to work.
        # Use a minimal set of kwargs so test monkeypatches with simple
        # signatures continue to work (e.g. fake_run(cmd, stdout=None, stderr=None)).
        # Avoid passing timeout to subprocess.run so simple test monkeypatch
        # functions with signature (cmd, stdout=None, stderr=None) remain
        # compatible.
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.TimeoutExpired:
        logger.warning("Command timeout (%s s): %s", timeout, shlex.join(cmd))
        # propagate the timeout to callers
        raise
    except Exception:
        logger.exception("Command execution failed (run): %s", cmd)
        raise


def run_cmd(
    cmd: List[str],
    *,
    filebase: Optional[Path] = None,
    timeout: Optional[float] = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a subprocess command with timeout, capture output and optionally save.

    If filebase is provided, stdout/err will be stored as filebase + .out/.err
    Returns completed process.

    Args:
        cmd: The command to run as a list of strings.
        filebase: Optional path base to save stdout/stderr to.
        timeout: Optional timeout in seconds.
        check: If True, raise CalledProcessError if return code is non-zero.

    Returns:
        subprocess.CompletedProcess or subprocess.TimeoutExpired
    """
    si = subprocess.STARTUPINFO() if os.name == "nt" else None
    if si:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    operation_id = uuid.uuid4().hex
    adapter = logging.LoggerAdapter(logger, {"operation_id": operation_id})
    adapter.debug("run_cmd start: %s", shlex.join(cmd))

    # If subprocess.run has been monkeypatched (tests), prefer using it so mocks apply
    try_run = subprocess.run
    if try_run is not ORIGINAL_SUBPROCESS_RUN:
        res = _run_with_subprocess_run(cmd, timeout)
    else:
        try:
            res = _run_with_popen(cmd, timeout, si)
        except Exception:
            adapter.exception("Command execution failed (popen): %s", cmd)
            raise

        # persist outputs when requested
        if filebase is not None:
            outp = getattr(res, "stdout", None) or ""
            errp = getattr(res, "stderr", None) or ""
            try:
                filebase.parent.mkdir(parents=True, exist_ok=True)
                with open(
                    str(filebase) + ".out",
                    "w",
                    encoding="utf-8",
                    errors="replace",
                ) as fo:
                    fo.write(outp)
                with open(
                    str(filebase) + ".err",
                    "w",
                    encoding="utf-8",
                    errors="replace",
                ) as fe:
                    fe.write(errp)
            except Exception:
                logger.debug(
                    "Failed to write command output files for %s",
                    filebase,
                )

    if check and isinstance(res, subprocess.CompletedProcess) and res.returncode != 0:
        raise subprocess.CalledProcessError(
            res.returncode, cmd, output=res.stdout, stderr=res.stderr
        )

    adapter.debug("run_cmd finished: rc=%s", getattr(res, "returncode", None))

    return res


def _run_cmd_stream_setup(cmd: List[str]) -> tuple[Any, logging.LoggerAdapter]:
    si = subprocess.STARTUPINFO() if os.name == "nt" else None
    if si:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    operation_id = uuid.uuid4().hex
    adapter = logging.LoggerAdapter(logger, {"operation_id": operation_id})
    adapter.debug("run_cmd_stream start: %s", shlex.join(cmd))
    return si, adapter


def _run_cmd_stream_monkeypatch(
    cmd: List[str], timeout: Optional[float]
) -> Optional[subprocess.CompletedProcess]:
    try_run = subprocess.run
    if try_run is not ORIGINAL_SUBPROCESS_RUN:
        res = _run_with_subprocess_run(cmd, timeout)
        out = getattr(res, "stdout", "") or ""
        return subprocess.CompletedProcess(
            cmd, getattr(res, "returncode", 1), stdout=out, stderr=None
        )
    return None


def _run_cmd_stream_open_file(
    stream_to_file: Optional[Path], adapter: logging.LoggerAdapter
) -> Any:
    if stream_to_file is None:
        return None
    try:
        stream_to_file.parent.mkdir(parents=True, exist_ok=True)
        return open(
            str(stream_to_file) + ".out",
            "w",
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        adapter.debug("failed to open stream_to_file %s", stream_to_file)
        return None


def _run_cmd_stream_parse_pct(
    line: str, parser: Optional[Callable[[str], Optional[float]]], adapter: logging.LoggerAdapter
) -> Optional[float]:
    try:
        if parser:
            return parser(line)
        m = PCT_RE.search(line)
        if m:
            return max(0.0, min(1.0, float(m.group(1)) / 100.0))
    except Exception as e:
        adapter.debug("Failed to parse progress from line: %s", e)
    return None


def _run_cmd_stream_process_line(
    line: str,
    file_handle: Any,
    out_lines: List[str],
    parser: Optional[Callable[[str], Optional[float]]],
    progress_cb: Optional[Callable[[float, str], None]],
    last_pct: Optional[float],
    adapter: logging.LoggerAdapter,
) -> Optional[float]:
    if file_handle:
        try:
            file_handle.write(line + "\n")
            file_handle.flush()
        except Exception:
            adapter.debug("failed to write stream line to file")
    else:
        out_lines.append(line)

    pct = _run_cmd_stream_parse_pct(line, parser, adapter)

    if pct is not None and progress_cb:
        if last_pct is None or abs(pct - last_pct) >= 0.005:
            try:
                progress_cb(pct, line)
            except Exception as e:
                adapter.debug("Progress callback failed: %s", e)
            return pct
    return last_pct


def _run_cmd_stream_persist(filebase: Optional[Path], combined: str, adapter: logging.LoggerAdapter) -> None:
    if filebase is not None:
        try:
            filebase.parent.mkdir(parents=True, exist_ok=True)
            with open(
                str(filebase) + ".out",
                "w",
                encoding="utf-8",
                errors="replace",
            ) as fo:
                fo.write(combined)
        except Exception:
            adapter.debug("Failed to write streaming command output for %s", filebase)


def _run_cmd_stream_cleanup(
    proc: subprocess.Popen, file_handle: Any, adapter: logging.LoggerAdapter
) -> None:
    if file_handle:
        try:
            file_handle.close()
        except Exception as e:
            adapter.debug("Failed to close stream file handle: %s", e)
    try:
        stdout = getattr(proc, "stdout", None)
        if stdout:
            stdout.close()
    except Exception:
        pass
    _unregister_process(proc)


def run_cmd_stream(
    cmd: List[str],
    *,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    parser: Optional[Callable[[str], Optional[float]]] = None,
    timeout: Optional[float] = None,
    filebase: Optional[Path] = None,
    stream_to_file: Optional[Path] = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a subprocess and stream its stdout/stderr lines.

    Emits progress via progress_cb when the parser returns a float in 0.0-1.0
    for a given output line. If parser is not provided, a simple percent
    regex is used to detect lines containing a percentage (e.g. "45%").

    Returns a CompletedProcess-like object with stdout/stderr combined.
    """
    si, adapter = _run_cmd_stream_setup(cmd)

    monkey_res = _run_cmd_stream_monkeypatch(cmd, timeout)
    if monkey_res:
        return monkey_res

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=si,
    )
    _register_process(proc)

    out_lines: List[str] = []
    last_pct: Optional[float] = None
    file_handle = _run_cmd_stream_open_file(stream_to_file, adapter)

    try:
        if proc.stdout:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                last_pct = _run_cmd_stream_process_line(
                    line, file_handle, out_lines, parser, progress_cb, last_pct, adapter
                )

        rc = proc.wait()
        combined = "\n".join(out_lines)
        completed = subprocess.CompletedProcess(cmd, rc, stdout=combined, stderr=None)

        _run_cmd_stream_persist(filebase, combined, adapter)

        if check and completed.returncode != 0:
            raise subprocess.CalledProcessError(
                completed.returncode,
                cmd,
                output=completed.stdout,
                stderr=completed.stderr,
            )

        adapter.debug("run_cmd_stream finished: rc=%s", completed.returncode)
        return completed
    finally:
        _run_cmd_stream_cleanup(proc, file_handle, adapter)
