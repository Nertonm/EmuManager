import pytest
from unittest.mock import MagicMock, patch
from emumanager.verification.dat_downloader import DatDownloader


@pytest.fixture
def mock_session():
    with patch("requests.Session") as mock:
        yield mock.return_value


def test_list_available_dats(mock_session, tmp_path):
    downloader = DatDownloader(tmp_path)

    # Mock API response
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"name": "Nintendo - Game Boy.dat", "type": "file"},
        {"name": "readme.md", "type": "file"},
        {"name": "subdir", "type": "dir"}
    ]
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response

    dats = downloader.list_available_dats("no-intro")

    assert len(dats) == 1
    assert "Nintendo - Game Boy.dat" in dats
    mock_session.get.assert_called_once()
    assert "api.github.com" in mock_session.get.call_args[0][0]


def test_download_dat(mock_session, tmp_path):
    downloader = DatDownloader(tmp_path)

    # Mock Raw content response
    mock_response = MagicMock()
    mock_response.content = b"xml content"
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response

    dest = downloader.download_dat("no-intro", "Nintendo - Game Boy.dat")

    assert dest is not None
    assert dest.exists()
    assert dest.read_bytes() == b"xml content"
    assert dest.parent.name == "no-intro"


def test_download_all(mock_session, tmp_path):
    downloader = DatDownloader(tmp_path)

    # Mock list response
    mock_list_resp = MagicMock()
    mock_list_resp.json.return_value = [
        {"name": "file1.dat", "type": "file"},
        {"name": "file2.dat", "type": "file"}
    ]

    # Mock download response
    mock_dl_resp = MagicMock()
    mock_dl_resp.content = b"data"

    # Configure side_effect to return different responses based on URL
    def side_effect(url, **kwargs):
        if "api.github.com" in url:
            return mock_list_resp
        return mock_dl_resp

    mock_session.get.side_effect = side_effect

    progress_mock = MagicMock()
    count = downloader.download_all(
        "no-intro", max_workers=2, progress_callback=progress_mock
    )

    assert count == 2
    assert (tmp_path / "no-intro" / "file1.dat").exists()
    assert (tmp_path / "no-intro" / "file2.dat").exists()
    assert progress_mock.call_count == 2
