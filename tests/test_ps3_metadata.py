import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from emumanager.common.sfo import SfoParser
from emumanager.ps3 import metadata


class TestSfoParser(unittest.TestCase):
    def test_parse_simple(self):
        # Construct a minimal SFO
        # Header: Magic(4) + Version(4) + KeyTableStart(4) + DataTableStart(4) + Num
        # Entry: KeyOffset(2) + Fmt(2) + Len(4) + MaxLen(4) + DataOffset(4)

        # Let's make a fake SFO with TITLE_ID = BLUS12345
        # Key: "TITLE_ID" (8 bytes + null)
        # Data: "BLUS12345" (9 bytes + null)

        magic = b"\x00PSF"
        version = b"\x01\x01\x00\x00"
        key_table_start = b"\x24\x00\x00\x00"
        data_table_start = b"\x2d\x00\x00\x00"
        num_entries = b"\x01\x00\x00\x00"

        header = magic + version + key_table_start + data_table_start + num_entries

        # Entry 0
        key_offset = b"\x00\x00"
        data_fmt = b"\x04\x02"
        data_len = b"\x0a\x00\x00\x00"
        data_max_len = b"\x0a\x00\x00\x00"
        data_offset = b"\x00\x00\x00\x00"

        entry = key_offset + data_fmt + data_len + data_max_len + data_offset

        key_table = b"TITLE_ID\x00"
        data_table = b"BLUS12345\x00"

        sfo_data = header + entry + key_table + data_table

        parser = SfoParser(sfo_data)
        self.assertEqual(parser.get("TITLE_ID"), "BLUS12345")


class TestPs3Metadata(unittest.TestCase):
    def test_regex_filename(self):
        p = Path("/roms/ps3/My Game [BLUS12345].iso")
        # Mock is_file/is_dir to avoid FS access and force regex path
        with (
            patch("pathlib.Path.is_file", return_value=True),
            patch("pathlib.Path.is_dir", return_value=False),
            patch("builtins.open", side_effect=Exception("No file access")),
        ):
            # Note: get_metadata tries to scan file if it's .iso.
            # If open fails, it catches Exception and proceeds to regex.
            meta = metadata.get_metadata(p)
        self.assertEqual(meta["serial"], "BLUS12345")

    def test_regex_filename_dash(self):
        p = Path("/roms/ps3/My Game [BLUS-12345].iso")
        with (
            patch("pathlib.Path.is_file", return_value=True),
            patch("pathlib.Path.is_dir", return_value=False),
            patch("builtins.open", side_effect=Exception("No file access")),
        ):
            meta = metadata.get_metadata(p)
        self.assertEqual(meta["serial"], "BLUS12345")

    @patch("emumanager.ps3.metadata.SfoParser")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    def test_folder_sfo(self, mock_is_dir, mock_exists, mock_open, mock_parser):
        mock_is_dir.return_value = True
        mock_exists.return_value = True

        mock_instance = mock_parser.return_value
        mock_instance.get.side_effect = lambda k: {"TITLE_ID": "BLUS12345"}.get(k)

        p = Path("/roms/ps3/MyGame")
        meta = metadata.get_metadata(p)

        self.assertEqual(meta["serial"], "BLUS12345")
        mock_open.assert_called()

    @patch("emumanager.ps3.metadata.SfoParser")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.is_dir")
    def test_iso_scan(self, mock_is_dir, mock_is_file, mock_open, mock_parser):
        # Setup
        mock_is_dir.return_value = False
        mock_is_file.return_value = True

        # Mock file content with SFO magic
        magic = b"\x00PSF\x01\x01\x00\x00"
        # Create a buffer where magic is found
        file_content = b"junk" * 100 + magic + b"sfo_data"

        file_handle = MagicMock()
        file_handle.read.return_value = file_content
        mock_open.return_value.__enter__.return_value = file_handle

        mock_instance = mock_parser.return_value
        mock_instance.get.side_effect = lambda k: {"TITLE_ID": "NPUB12345"}.get(k)

        # Execute
        path = Path("/games/game.iso")
        meta = metadata.get_metadata(path)

        # Verify
        self.assertEqual(meta["serial"], "NPUB12345")
        # Should have read the file
        mock_open.assert_called_with(path, "rb")
