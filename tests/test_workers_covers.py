import pytest; pytest.importorskip("PyQt6")
from unittest.mock import MagicMock, patch

import pytest

from emumanager.workers.covers import CoverDownloader


@pytest.fixture
def mock_requests_get():
    with patch("requests.get") as mock:
        yield mock


def test_cover_downloader_no_game_id(tmp_path):
    downloader = CoverDownloader("switch", None, "US", str(tmp_path))
    mock_signal = MagicMock()
    downloader.signals.finished.connect(mock_signal)
    downloader.run()
    # PyQt signal(str) converts None to ""
    mock_signal.assert_called_once_with("")


def test_cover_downloader_cache_hit(tmp_path):
    cache_dir = tmp_path / "cache"
    game_id = "TEST1234"
    system = "switch"

    # Create fake cache file
    cover_dir = cache_dir / "covers" / system
    cover_dir.mkdir(parents=True)
    cover_file = cover_dir / f"{game_id}.jpg"
    cover_file.touch()

    downloader = CoverDownloader(system, game_id, "US", str(cache_dir))
    mock_signal = MagicMock()
    downloader.signals.finished.connect(mock_signal)
    downloader.run()

    mock_signal.assert_called_once_with(str(cover_file))


def test_cover_downloader_download_success(tmp_path, mock_requests_get):
    cache_dir = tmp_path / "cache"
    game_id = "TEST1234"
    system = "switch"

    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"fake_image_data"
    mock_requests_get.return_value = mock_response

    downloader = CoverDownloader(system, game_id, "US", str(cache_dir))
    mock_signal = MagicMock()
    downloader.signals.finished.connect(mock_signal)
    downloader.run()

    # It tries png first
    expected_path = cache_dir / "covers" / system / f"{game_id}.png"
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"fake_image_data"
    mock_signal.assert_called_once_with(str(expected_path))


def test_cover_downloader_download_failure(tmp_path, mock_requests_get):
    cache_dir = tmp_path / "cache"
    game_id = "TEST1234"
    system = "switch"

    # Mock response 404
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    downloader = CoverDownloader(system, game_id, "US", str(cache_dir))
    mock_signal = MagicMock()
    downloader.signals.finished.connect(mock_signal)
    downloader.run()

    mock_signal.assert_called_once_with("")


def test_cover_downloader_gamecube_mapping(tmp_path, mock_requests_get):
    cache_dir = tmp_path / "cache"
    game_id = "GCN123"
    system = "gamecube"

    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"data"
    mock_requests_get.return_value = mock_response

    downloader = CoverDownloader(system, game_id, "US", str(cache_dir))
    mock_signal = MagicMock()
    downloader.signals.finished.connect(mock_signal)
    downloader.run()

    # Should map gamecube to wii in URL and path
    args, _ = mock_requests_get.call_args
    assert "/wii/" in args[0]

    expected_path = cache_dir / "covers" / "wii" / f"{game_id}.png"
    assert expected_path.exists()


def test_cover_downloader_exception(tmp_path, mock_requests_get):
    mock_requests_get.side_effect = Exception("Network error")

    downloader = CoverDownloader("switch", "ID", "US", str(tmp_path))
    mock_signal = MagicMock()
    downloader.signals.finished.connect(mock_signal)
    downloader.run()

    mock_signal.assert_called_once_with("")
