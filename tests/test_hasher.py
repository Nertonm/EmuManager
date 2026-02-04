from emumanager.verification.hasher import calculate_hashes

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
