from pathlib import Path
import types

from emumanager.switch import main_helpers as mh


class DummyArgs:
    dry_run = False
    keep_on_failure = False


def make_ctx(tmp_path, *, move_result=True, meta=None):
    roms = tmp_path

    def get_metadata(p):
        return meta

    def sanitize_name(n):
        return n.replace(" ", "_")

    def determine_region(tid):
        return "(World)"

    def handle_compression(p):
        return p

    def safe_move(src, dst):
        # simulate creating the parent dirs and returning move_result
        dst.parent.mkdir(parents=True, exist_ok=True)
        if move_result:
            src_path = Path(src)
            # if src exists, move (simulate)
            try:
                src_path.rename(dst)
            except Exception:
                # if rename fails because both are same, ignore
                pass
            return True
        return False

    return {
        "ROMS_DIR": roms,
        "get_metadata": get_metadata,
        "sanitize_name": sanitize_name,
        "determine_region": determine_region,
        "handle_compression": handle_compression,
        "safe_move": safe_move,
        "logger": types.SimpleNamespace(info=print, warning=print, debug=print, exception=print),
    }


def test_process_one_file_success(tmp_path):
    f = tmp_path / "Game [0100ABCDEF000020].nsp"
    f.write_text("data")
    meta = {"id": "0100ABCDEF000020", "name": "Game", "ver": "v1", "langs": "En", "type": "Base"}
    ctx = make_ctx(tmp_path, move_result=True, meta=meta)

    row, status = mh.process_one_file(f, ctx)
    assert status == "ok"
    assert row is not None
    assert row[1] == meta["id"]


def test_process_one_file_missing_meta(tmp_path):
    f = tmp_path / "Broken.nsp"
    f.write_text("data")
    ctx = make_ctx(tmp_path, move_result=True, meta=None)

    row, status = mh.process_one_file(f, ctx)
    assert status == "error"
    assert row is None
