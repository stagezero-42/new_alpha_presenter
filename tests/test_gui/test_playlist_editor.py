# tests/test_gui/test_playlist_editor.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
# --- MODIFIED: Import QPushButton ---
from PySide6.QtWidgets import QApplication, QPushButton
# --- END MODIFIED ---

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.playlist_editor import PlaylistEditorWindow
from myapp.playlist.playlist import Playlist

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

@pytest.fixture
def mock_display_window():
    return MagicMock()

@pytest.fixture
def playlist_editor(qapp, mock_display_window, tmp_path):
    playlist = Playlist()
    # --- MODIFIED: Patch sources, DO NOT mock create_button ---
    with patch('myapp.utils.paths.get_playlists_path', return_value=str(tmp_path)):
        # Patch get_icon_file_path at its source
        with patch('myapp.utils.paths.get_icon_file_path', return_value="dummy_icon.png"):
             # Mock QIcon inside widget_helpers where create_button uses it
             with patch('myapp.gui.widget_helpers.QIcon'):
                 # Patch LayerEditorDialog to avoid its full setup in these specific tests
                 with patch('myapp.gui.playlist_editor.LayerEditorDialog'):
                     with patch('myapp.utils.paths.get_media_path', return_value=str(tmp_path)):
                         window = PlaylistEditorWindow(
                             mock_display_window,
                             playlist,
                             None
                         )
    # --- END MODIFIED ---
    return window

def test_playlist_editor_creation(playlist_editor):
    assert playlist_editor is not None
    assert "Playlist Editor" in playlist_editor.windowTitle()

def test_playlist_editor_buttons(playlist_editor):
    assert playlist_editor.new_button is not None
    assert isinstance(playlist_editor.new_button, QPushButton) # Check it's a real button
    assert playlist_editor.load_button is not None
    assert playlist_editor.save_button is not None
    assert playlist_editor.save_as_button is not None
    assert playlist_editor.done_button is not None