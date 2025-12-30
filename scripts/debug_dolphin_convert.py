#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure project package dir is first on sys.path to avoid local script name collisions
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from emumanager.workers.dolphin import worker_dolphin_convert  # noqa: E402


def log_cb(msg: str):
    print(msg)


def list_files_fn(d: Path):
    # list immediate files (not recursive) to match worker expectations
    return [p for p in d.iterdir() if p.is_file()]


class Args:
    progress_callback = None
    cancel_event = None
    rm_originals = False


if __name__ == "__main__":
    base = Path.cwd()
    print(f"Running dolphin convert worker with base: {base}")
    try:
        res = worker_dolphin_convert(base, Args(), log_cb, list_files_fn)
        print("WORKER RESULT:", res)
    except Exception as e:
        print("EXCEPTION:", e)
        import traceback

        traceback.print_exc()
        sys.exit(1)
