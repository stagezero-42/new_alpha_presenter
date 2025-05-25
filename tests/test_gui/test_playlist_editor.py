# tests/test_gui/test_playlist_editor.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

# Ensure myapp is in path for imports like myapp.gui.playlist_editor
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.playlist_editor import PlaylistEditorWindow
from myapp.playlist.playlist import Playlist
# SettingsManager is no longer needed for this test file directly

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

@pytest.fixture
def mock_display_window():
    return MagicMock()

# mock_settings_manager fixture is no longer needed here

@pytest.fixture
def playlist_editor(qapp, mock_display_window, tmp_path): # Removed mock_settings_manager
    playlist = Playlist()
    # Patch paths used within PlaylistEditorWindow
    with patch('myapp.gui.playlist_editor.get_playlists_path', return_value=str(tmp_path)):
        with patch('myapp.gui.playlist_editor.get_icon_file_path', return_value="dummy_icon.png"):
             # --- MODIFIED: Call with correct arguments ---
             # PlaylistEditorWindow(display_window_instance, playlist_obj, parent=None)
             window = PlaylistEditorWindow(
                 mock_display_window,
                 playlist,
                 None  # Pass None for the parent argument
             )
             # --- END MODIFIED ---
    return window

def test_playlist_editor_creation(playlist_editor):
    assert playlist_editor is not None
    assert "Playlist Editor" in playlist_editor.windowTitle()

def test_playlist_editor_buttons(playlist_editor):
    assert playlist_editor.new_button is not None
    assert playlist_editor.load_button is not None
    assert playlist_editor.save_button is not None
    assert playlist_editor.save_as_button is not None
    # assert playlist_editor.settings_button is not None # This button was removed
    assert playlist_editor.done_button is not None

# test_open_keybindings_editor was removed as the feature was removed