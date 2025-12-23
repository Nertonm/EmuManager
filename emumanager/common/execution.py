import subprocess
import os
import logging
import threading
from pathlib import Path
from typing import Optional, List, Union, Set, Any
import shutil

logger = logging.getLogger(__name__)

_RUNNING_PROCESSES: Set[subprocess.Popen] = set()
_LOCK = threading.Lock()
ORIGINAL_SUBPROCESS_RUN = subprocess.run

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
        except Exception:
            try:
                proc.terminate()
                cancelled_any = True
            except Exception:
                pass
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

def _run_with_popen(cmd: List[str], timeout: Optional[int], si: Any) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        startupinfo=si,
    )
    _register_process(proc)
    try:
        out, err = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr=err)
    except subprocess.TimeoutExpired:
        logger.warning("Command timeout (%s s): %s", timeout, " ".join(map(str, cmd)))
        try:
            proc.kill()
        except Exception:
            logger.debug("Failed to kill timed-out subprocess")
        out, err = proc.communicate()
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr=err)
    finally:
        _unregister_process(proc)


def _run_with_subprocess_run(cmd: List[str], timeout: Optional[int]) -> Union[subprocess.CompletedProcess, subprocess.TimeoutExpired]:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        logger.warning("Command timeout (%s s): %s", timeout, " ".join(map(str, cmd)))
        return e
    except Exception:
        logger.exception("Command execution failed (run): %s", cmd)
        raise


def run_cmd(
    cmd: List[str], 
    *, 
    filebase: Optional[Path] = None, 
    timeout: Optional[int] = None, 
    check: bool = False
) -> Union[subprocess.CompletedProcess, subprocess.TimeoutExpired]:
    """Run a subprocess command with timeout, capture output and optionally save to files.

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

    # If subprocess.run has been monkeypatched (tests), prefer using it so mocks apply
    try_run = subprocess.run
    if try_run is not ORIGINAL_SUBPROCESS_RUN:
        res = _run_with_subprocess_run(cmd, timeout)
    else:
        try:
            res = _run_with_popen(cmd, timeout, si)
        except Exception:
            logger.exception("Command execution failed (popen): %s", cmd)
            raise

    # persist outputs when requested
    if filebase is not None:
        outp = getattr(res, "stdout", None) or ""
        errp = getattr(res, "stderr", None) or ""
        try:
            filebase.parent.mkdir(parents=True, exist_ok=True)
            with open(str(filebase) + ".out", "w", encoding="utf-8", errors="ignore") as fo:
                fo.write(outp)
            with open(str(filebase) + ".err", "w", encoding="utf-8", errors="ignore") as fe:
                fe.write(errp)
        except Exception:
            logger.debug("Failed to write command output files for %s", filebase)

    if check and isinstance(res, subprocess.CompletedProcess) and res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)
    
    return res
