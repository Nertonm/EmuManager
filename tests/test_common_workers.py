from unittest.mock import MagicMock

from emumanager.workers.common import (_clean_junk_files, calculate_file_hash,
                                       create_file_progress_cb,
                                       find_target_dir, worker_clean_junk)


def test_calculate_file_hash(tmp_path):
    # Create a dummy file
    f = tmp_path / "test.bin"
    content = b"test content" * 100
    f.write_bytes(content)

    # Calculate hash without progress
    hash_md5 = calculate_file_hash(f, algo="md5")
    assert len(hash_md5) == 32

    # Calculate hash with progress
    progress_cb = MagicMock()
    hash_sha1 = calculate_file_hash(
        f, algo="sha1", chunk_size=10, progress_cb=progress_cb
    )
    assert len(hash_sha1) == 40
    assert progress_cb.called
    # Check if progress reached 1.0 (approx)
    assert abs(progress_cb.call_args[0][0] - 1.0) < 0.001


def test_create_file_progress_cb():
    main_cb = MagicMock()

    # File represents 50% of total, starting at 0.0
    file_cb = create_file_progress_cb(
        main_cb, start_prog=0.0, file_weight=0.5, filename="test.iso"
    )

    file_cb(0.0)
    main_cb.assert_called_with(0.0, "Processing test.iso (0%)...")

    file_cb(0.5)
    main_cb.assert_called_with(0.25, "Processing test.iso (50%)...")

    file_cb(1.0)
    main_cb.assert_called_with(0.5, "Processing test.iso (100%)...")


def test_find_target_dir(tmp_path):
    # Setup structure
    (tmp_path / "roms" / "ps2").mkdir(parents=True)
    (tmp_path / "gamecube").mkdir()

    # Test finding nested
    res = find_target_dir(tmp_path, ["roms/ps2", "ps2"])
    assert res == tmp_path / "roms" / "ps2"

    # Test finding direct
    res = find_target_dir(tmp_path, ["gamecube"])
    assert res == tmp_path / "gamecube"

    # Test fallback (if base_path IS the target)
    res = find_target_dir(tmp_path / "gamecube", ["gamecube"])
    assert res == tmp_path / "gamecube"

    # Test not found
    res = find_target_dir(tmp_path, ["wii"])
    assert res is None


def test_worker_clean_junk(tmp_path):
    # Setup
    base = tmp_path / "collection"
    base.mkdir()

    # Junk files
    (base / "info.txt").touch()
    (base / "site.url").touch()
    (base / "game.iso").touch()  # Keep this

    # Empty dirs
    (base / "empty_dir").mkdir()
    (base / "nested" / "empty").mkdir(parents=True)
    (base / "full_dir").mkdir()
    (base / "full_dir" / "game.bin").touch()

    args = MagicMock()
    args.dry_run = False
    args.progress_callback = MagicMock()

    def list_files(p):
        return list(p.rglob("*")) if p.is_dir() else []

    def list_dirs(p):
        return [x for x in p.rglob("*") if x.is_dir()]

    res = worker_clean_junk(base, args, lambda x: None, list_files, list_dirs)

    print(f"DEBUG: res='{res}'")
    assert res == "Cleanup complete. Deleted 2 files and 3 empty directories."

    assert not (base / "info.txt").exists()
    assert not (base / "site.url").exists()
    assert (base / "game.iso").exists()
    assert not (base / "empty_dir").exists()
    assert (base / "full_dir").exists()


def test_clean_junk_files_internal(tmp_path):
    # Setup files
    f1 = tmp_path / "readme.txt"
    f1.touch()
    f2 = tmp_path / "game.iso"
    f2.touch()
    f3 = tmp_path / "site.url"
    f3.touch()

    files = [f1, f2, f3]
    mock_logger = MagicMock()

    # Execute
    count = _clean_junk_files(files, None, mock_logger)

    # Verify
    assert count == 2  # txt and url
    assert not f1.exists()
    assert f2.exists()
    assert not f3.exists()
