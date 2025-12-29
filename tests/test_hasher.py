from emumanager.verification.hasher import (_finalize_hashes,
                                            _init_hash_objects, _update_hashes,
                                            calculate_hashes)


def test_init_hash_objects():
    objs = _init_hash_objects(("crc32", "md5", "sha1"))
    assert "crc32" in objs
    assert "md5" in objs
    assert "sha1" in objs
    assert objs["crc32"] == 0


def test_update_hashes():
    objs = _init_hash_objects(("crc32", "md5"))
    data = b"123456789"
    _update_hashes(objs, data)

    # CRC32 of "123456789" is 0xcbf43926
    assert objs["crc32"] == 0xCBF43926
    # MD5 check
    assert objs["md5"].hexdigest() == "25f9e794323b453885f5181f1b624d0b"


def test_finalize_hashes():
    objs = _init_hash_objects(("crc32",))
    data = b"123456789"
    _update_hashes(objs, data)
    res = _finalize_hashes(objs)

    assert res["crc32"] == "cbf43926"


def test_calculate_hashes_file(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"123456789")

    hashes = calculate_hashes(f, algorithms=("crc32", "md5", "sha1"))

    assert hashes["crc32"] == "cbf43926"
    assert hashes["md5"] == "25f9e794323b453885f5181f1b624d0b"
    # Correct SHA1 for "123456789"
    assert hashes["sha1"] == "f7c3bc1d808e04732adf679965ccc34ca7ae3441"


def test_calculate_hashes_empty_file(tmp_path):
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")

    hashes = calculate_hashes(f, algorithms=("crc32",))
    assert hashes["crc32"] == "00000000"
