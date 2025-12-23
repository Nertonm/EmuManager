"""Metadata extraction and decompression orchestration.

Exports a testable function `get_metadata_info` that runs a metadata tool
and optionally falls back to decompressing NSZ/XCZ files to extract inner
NSP/XCI metadata. All external actions (running commands, file system
locations) are provided as parameters so the function stays testable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable
import re
from emumanager.switch.pfs0 import SwitchPFS0Parser

REGEX_TITLE_ID = r"\[([0-9a-fA-F]{16})\]"
REGEX_VERSION = r"[\[\(]v?(\d+|[\d\.]+)[\)\]]"
REGEX_BRACKETS = r"\[[^\]]*\]"


def _try_decompress(
    tool_nsz: Path,
    filepath: Path,
    tmpdir: Path,
    base: Path,
    run_cmd: Callable,
    cmd_timeout: Optional[int]
) -> Optional[Path]:
    attempts = [
        [str(tool_nsz), "-D", "-o", str(tmpdir), str(filepath)],
        [str(tool_nsz), "-D", "--out", str(tmpdir), str(filepath)],
        [str(tool_nsz), "-D", str(filepath), "-o", str(tmpdir)],
        [str(tool_nsz), "-D", str(filepath), "--out", str(tmpdir)],
        [str(tool_nsz), "-D", str(filepath), str(tmpdir)],
    ]
    for cmd in attempts:
        try:
            logbase = Path(base) / "logs" / "nsz" / (filepath.stem + ".decomp")
            _ = run_cmd(cmd, filebase=logbase, timeout=cmd_timeout)
        except Exception:
            continue

        for ext in (".nsp", ".xci"):
            found = list(Path(tmpdir).rglob(f"*{ext}"))
            if found:
                return found[0]
    return None


def _extract_with_tool(
    filepath: Path,
    tool_metadata: Path,
    is_nstool: bool,
    keys_path: Optional[Path],
    cmd_timeout: Optional[int],
    base: Path,
    run_cmd: Callable,
    parse_tool_output: Callable,
    parse_languages: Callable,
    detect_languages_from_filename: Callable,
    determine_type: Callable,
) -> Optional[dict]:
    try:
        cmd = [str(tool_metadata), "-v" if is_nstool else "-k", str(filepath)]
        if not is_nstool:
            cmd.insert(2, str(keys_path))
            cmd.insert(3, "-i")

        logbase = Path(base) / "logs" / "nsz" / (filepath.stem + ".meta")
        res = run_cmd(cmd, filebase=logbase, timeout=cmd_timeout)
        parsed = parse_tool_output(getattr(res, "stdout", ""))
        if parsed.get("name") and parsed.get("id"):
            info = {}
            info["name"] = parsed.get("name")
            info["id"] = parsed.get("id").upper() if parsed.get("id") else None
            info["ver"] = parsed.get("ver") or "v0"
            langs_raw = parsed.get("langs") or parse_languages(getattr(res, "stdout", "")) or detect_languages_from_filename(filepath.name)
            if langs_raw and langs_raw.startswith("[") and langs_raw.endswith("]"):
                langs_raw = langs_raw[1:-1]
            info["langs"] = langs_raw
            info["type"] = determine_type(info["id"], getattr(res, "stdout", ""))
            return info
    except Exception:
        pass
    return None


def _extract_with_decompression(
    filepath: Path,
    tool_nsz: Path,
    tool_metadata: Path,
    is_nstool: bool,
    keys_path: Optional[Path],
    cmd_timeout: Optional[int],
    base: Path,
    run_cmd: Callable,
    parse_tool_output: Callable,
    parse_languages: Callable,
    detect_languages_from_filename: Callable,
    determine_type: Callable,
) -> Optional[dict]:
    try:
        if filepath.suffix.lower() in {".nsz", ".xcz"}:
            import tempfile

            with tempfile.TemporaryDirectory(prefix="nsz_extract_") as td:
                tmpdir = Path(td)
                decompressed = _try_decompress(tool_nsz, filepath, tmpdir, base, run_cmd, cmd_timeout)
                
                if decompressed and decompressed.exists():
                    return _extract_with_tool(
                        decompressed,
                        tool_metadata,
                        is_nstool,
                        keys_path,
                        cmd_timeout,
                        base,
                        run_cmd,
                        parse_tool_output,
                        parse_languages,
                        detect_languages_from_filename,
                        determine_type,
                    )
    except Exception:
        pass
    return None


def _extract_with_native_parser(
    filepath: Path,
    determine_type: Callable,
) -> Optional[dict]:
    try:
        parser = SwitchPFS0Parser(filepath)
        tid = parser.get_title_id()
        if tid:
            info = {"name": None, "id": tid, "ver": "v0", "type": "DLC", "langs": ""}
            info["type"] = determine_type(tid, None)
            
            # Try to get version from filename if not found
            ver_match = re.search(REGEX_VERSION, filepath.name)
            if ver_match:
                info["ver"] = f"v{ver_match.group(1)}"
            
            # Try to get name from filename
            name_part = filepath.name.split(f"[{tid}]")[0]
            name_part = re.sub(REGEX_BRACKETS, "", name_part).strip()
            if name_part:
                info["name"] = name_part
            
            return info
    except Exception:
        pass
    return None


def get_metadata_info(
    filepath: Path,
    *,
    run_cmd: Callable,
    tool_metadata: Optional[Path],
    is_nstool: bool,
    keys_path: Optional[Path],
    tool_nsz: Optional[Path],
    roms_dir: Path,
    cmd_timeout: Optional[int],
    parse_tool_output: Callable[[Optional[str]], dict],
    parse_languages: Callable[[Optional[str]], str],
    detect_languages_from_filename: Callable[[str], str],
    determine_type: Callable[[Optional[str], Optional[str]], str],
) -> Optional[dict]:
    """Attempt to obtain metadata for `filepath` using the provided helpers.

    Returns an info dict {'name','id','ver','type','langs'} or None on failure.
    """
    info = {"name": None, "id": None, "ver": "v0", "type": "DLC", "langs": ""}
    base = roms_dir or Path(".")

    # Primary attempt: run metadata tool on the given file
    if tool_metadata:
        res = _extract_with_tool(
            filepath, tool_metadata, is_nstool, keys_path, cmd_timeout, base,
            run_cmd, parse_tool_output, parse_languages, detect_languages_from_filename, determine_type
        )
        if res:
            return res

        # Fallback: if compressed and TOOL_NSZ available
        if tool_nsz:
            res = _extract_with_decompression(
                filepath, tool_nsz, tool_metadata, is_nstool, keys_path, cmd_timeout, base,
                run_cmd, parse_tool_output, parse_languages, detect_languages_from_filename, determine_type
            )
            if res:
                return res

    # Secondary attempt: Native PFS0 parser
    res = _extract_with_native_parser(filepath, determine_type)
    if res:
        return res

    # Final fallback: try to parse titleid from filename
    try:
        tid_match = re.search(REGEX_TITLE_ID, filepath.name)
        if tid_match:
            clean_tid = tid_match.group(1).upper()
            name_part = filepath.name.split(f"[{clean_tid}]")[0]
            name_part = re.sub(REGEX_BRACKETS, "", name_part).strip()
            ver_match = re.search(REGEX_VERSION, filepath.name)
            info["name"] = name_part
            info["id"] = clean_tid
            if ver_match:
                info["ver"] = f"v{ver_match.group(1)}"
            info["type"] = determine_type(clean_tid, None)
            return info
    except Exception:
        pass

    return None