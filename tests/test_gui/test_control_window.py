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
from myapp.settings.settings_manager import SettingsManager

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
    """Creates a ControlWindow instance with mocked dependencies."""
    with patch('myapp.gui.control_window.SettingsManager') as MockSM:
        MockSM.return_value.get_current_playlist.return_value = None
        MockSM.return_value.get_setting.return_value = {}
        with patch('myapp.gui.control_window.os.path.exists', return_value=True): # For icon loading
            with patch('myapp.gui.control_window.get_icon_file_path', return_value="dummy.png"):
                with patch('myapp.gui.control_window.setup_keybindings') as mock_setup_keys:
                     window = ControlWindow(mock_media_renderer)
                     mock_setup_keys.assert_called_once_with(window, window.settings_manager)
    window.playlist = MagicMock(spec=Playlist)
    return window

@pytest.fixture
def valid_playlist_path(tmp_path):
    playlist_dir = tmp_path / "playlists"
    playlist_dir.mkdir()
    playlist_content = {"slides": [{"layers": ["image1.png"], "duration": 5, "loop_to_slide": 0}]}
    playlist_path = playlist_dir / "test_playlist.json"
    with open(playlist_path, "w") as f:
        json.dump(playlist_content, f)
    return str(playlist_path)

@patch('myapp.gui.control_window.get_themed_open_filename')
def test_load_playlist_dialog_opens_and_loads(mock_get_themed_open_filename, control_window, valid_playlist_path):
    mock_get_themed_open_filename.return_value = valid_playlist_path
    playlists_dir = os.path.dirname(valid_playlist_path)

    with patch('myapp.gui.control_window.get_playlists_path', return_value=playlists_dir):
         with patch.object(control_window, 'load_playlist') as mock_load:
              control_window.load_playlist_dialog()
              mock_get_themed_open_filename.assert_called_once_with(
                  control_window, "Open Playlist", playlists_dir, "JSON Files (*.json)"
              )
              mock_load.assert_called_once_with(valid_playlist_path)

# --- MODIFIED TEST ---
def test_next_slide_updates_state_and_attempts_display(control_window):
    control_window.playlist.get_slides.return_value = [
        {"layers": ["img1.png"], "duration": 5, "loop_to_slide": 0},
        {"layers": ["img2.png"], "duration": 0, "loop_to_slide": 0}
    ]
    control_window.current_index = 0 # Start at the first slide

    # We expect _display_current_slide to be called when next_slide successfully moves to a new slide
    with patch.object(control_window, '_display_current_slide') as mock_display_current:
        control_window.next_slide()
        # Assert that the index changed correctly
        assert control_window.current_index == 1
        # Assert that the method responsible for updating the display was called
        mock_display_current.assert_called_once()

    # Test boundary condition: already at the last slide
    control_window.current_index = 1 # Move to the last slide
    with patch.object(control_window, '_display_current_slide') as mock_display_current_again:
        control_window.next_slide()
        # Index should not change
        assert control_window.current_index == 1
        # Display method should NOT be called again
        mock_display_current_again.assert_not_called()
# --- END MODIFIED TEST ---