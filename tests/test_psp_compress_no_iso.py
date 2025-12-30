from emumanager.workers.psp import worker_psp_compress


class DummyArgs:
    rm_originals = False
    level = 9
    dry_run = False


def test_worker_psp_compress_no_iso(tmp_path):
    # Setup base with a PSP directory but no .iso files
    base = tmp_path
    psp_dir = base / "roms" / "psp"
    psp_dir.mkdir(parents=True)

    # create a non-ISO file
    (psp_dir / "readme.txt").write_text("no isos here")

    def list_files_fn(d):
        # Return the files present in the directory
        return list(psp_dir.iterdir())

    logs = []
    res = worker_psp_compress(
        base, DummyArgs(), lambda m: logs.append(m), list_files_fn
    )

    assert res == "No ISO files found to compress."
