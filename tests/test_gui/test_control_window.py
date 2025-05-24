# tests/test_gui/test_control_window.py
import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.control_window import ControlWindow
from myapp.media.media_renderer import MediaRenderer
from myapp.playlist.playlist import Playlist

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

@pytest.fixture
def mock_media_renderer():
    return MagicMock(spec=MediaRenderer)

@pytest.fixture
def control_window(qapp, mock_media_renderer):
    window = ControlWindow(mock_media_renderer)
    window.playlist = MagicMock(spec=Playlist)
    return window

@pytest.fixture
def valid_playlist_path(tmp_path):
    playlist_dir = tmp_path / "playlists"
    playlist_dir.mkdir()
    playlist_content = {"slides": [{"layers": ["image1.png"]}]}
    playlist_path = playlist_dir / "test_playlist.json"
    with open(playlist_path, "w") as f:
        json.dump(playlist_content, f)
    return playlist_path

@patch('PySide6.QtWidgets.QFileDialog.getOpenFileName')
def test_load_playlist_dialog_opens_and_loads(mock_get_open_file_name, control_window, valid_playlist_path):
    mock_get_open_file_name.return_value = (valid_playlist_path, "JSON Files (*.json)")

    with patch.object(control_window, 'load_playlist') as mock_load:
        control_window.load_playlist_dialog()
        mock_get_open_file_name.assert_called_once()
        mock_load.assert_called_once_with(valid_playlist_path)

def test_next_slide_calls_update_display(control_window):
    control_window.playlist.get_slides.return_value = [1, 2]
    control_window.current_index = 0
    with patch.object(control_window, 'update_display') as mock_update:
        control_window.next_slide()
        mock_update.assert_called_once()
        assert control_window.current_index == 1