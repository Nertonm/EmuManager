from emumanager.ps2.database import PS2Database


def test_database_empty():
    db = PS2Database()
    assert db.get_title("SLUS-20002") is None


def test_load_from_csv(tmp_path):
    csv_file = tmp_path / "db.csv"
    csv_file.write_text(
        "Serial,Title\nSLUS-20002,Ridge Racer V\nSLES-50003,Another Game"
    )

    db = PS2Database()
    db.load_from_csv(csv_file)

    assert db.get_title("SLUS-20002") == "Ridge Racer V"
    assert db.get_title("SLES-50003") == "Another Game"
    assert db.get_title("SLUS-99999") is None


def test_load_from_csv_normalization(tmp_path):
    # Test that DB normalizes input serials (e.g. SLUS_200.02 -> SLUS-20002)
    csv_file = tmp_path / "db.csv"
    # CSV might contain raw formats
    csv_file.write_text("SLUS_200.02,Game A\nSLUS20003,Game B")

    db = PS2Database()
    db.load_from_csv(csv_file)

    assert db.get_title("SLUS-20002") == "Game A"
    assert db.get_title("SLUS-20003") == "Game B"
