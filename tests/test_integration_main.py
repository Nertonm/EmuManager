from pathlib import Path

import emumanager.switch.cli as so


class Args:
    pass


def make_args(**kwargs):
    a = Args()
    # set defaults used by main
    a.dir = None
    a.keys = "./prod.keys"
    a.dry_run = False
    a.no_verify = False
    a.organize = False
    a.clean_junk = False
    a.compress = False
    a.decompress = False
    a.level = 1
    a.dup_check = "fast"
    a.verbose = False
    a.log_file = "organizer_v13.log"
    a.log_max_bytes = 5 * 1024 * 1024
    a.log_backups = 3
    a.health_check = False
    a.quarantine = False
    a.quarantine_dir = None
    a.deep_verify = False
    a.report_csv = None
    a.rm_originals = False

    for k, v in kwargs.items():
        setattr(a, k, v)
    return a


def test_main_compress_rm_dryrun(tmp_path, monkeypatch):
    # Create a fake ROM file
    rom = tmp_path / "Game [0100ABCDEF000020].nsp"
    rom.write_bytes(b"romdata")

    # Ensure find_tool returns something so main doesn't exit
    monkeypatch.setattr(so, "find_tool", lambda name: Path("/bin/true"))

    # Provide args: compress + rm_originals but dry_run=True
    args = make_args(dir=str(tmp_path), compress=True, rm_originals=True, dry_run=True)

    # Monkeypatch parser.parse_args to return our args
    monkeypatch.setattr(so.parser, "parse_args", lambda *a, **k: args)

    # Monkeypatch subprocess.run to simulate nsz (should not be called due to dry-run)
    def fake_run(cmd, **kwargs):
        raise RuntimeError("subprocess should not be called in dry-run")

    monkeypatch.setattr(so.subprocess, "run", fake_run)

    # Run main; should not raise
    so.main()

    # Original must still exist
    assert rom.exists()


def test_health_check_quarantine_report(tmp_path, monkeypatch):
    # setup two files
    good = tmp_path / "Good [0100ABCDEF000021].nsp"
    bad = tmp_path / "Bad [0100ABCDEF000022].nsp"
    good.write_bytes(b"good")
    bad.write_bytes(b"bad")

    monkeypatch.setattr(so, "find_tool", lambda name: Path("/bin/true"))

    args = make_args(
        dir=str(tmp_path),
        health_check=True,
        quarantine=True,
        report_csv=str(tmp_path / "report.csv"),
    )
    monkeypatch.setattr(so.parser, "parse_args", lambda *a, **k: args)

    # Monkeypatch verify_integrity: good->True, bad->False
    def fake_verify(f, deep=False, return_output=False, **kwargs):
        if isinstance(f, (str,)):
            p = Path(f)
        else:
            p = f
        if p.name.startswith("Good"):
            return (True, "ok") if return_output else True
        else:
            return (False, "corrupt") if return_output else False

    monkeypatch.setattr(so, "verify_integrity", fake_verify)

    # Monkeypatch scan_for_virus: none infected
    monkeypatch.setattr(so, "scan_for_virus", lambda f, **k: (False, "clean"))

    import pytest

    with pytest.raises(SystemExit) as excinfo:
        so.main()
    assert excinfo.value.code == 1

    # report should be written
    report = tmp_path / "report.csv"
    assert report.exists(), "Health-check should write report CSV"

    # quarantine dir should exist and contain bad file
    qdir = tmp_path / "_QUARANTINE"
    # since main moves only when not dry-run, the bad file should have been moved
    assert qdir.exists(), "Quarantine dir should be created"
    moved = any(p.name.startswith("Bad") for p in qdir.iterdir())
    assert moved, "Bad file should be quarantined"
