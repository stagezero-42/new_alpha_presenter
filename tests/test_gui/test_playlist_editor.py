# tests/test_gui/test_playlist_editor.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
# --- MODIFIED: Added QPushButton, QMessageBox ---
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox

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
    with patch('myapp.utils.paths.get_playlists_path', return_value=str(tmp_path)):
        with patch('myapp.utils.paths.get_icon_file_path', return_value="dummy_icon.png"):
             with patch('myapp.gui.widget_helpers.QIcon'):
                 with patch('myapp.gui.playlist_editor.LayerEditorDialog'):
                     with patch('myapp.utils.paths.get_media_path', return_value=str(tmp_path)):
                         window = PlaylistEditorWindow(
                             mock_display_window,
                             playlist,
                             None
                         )
    return window

def test_playlist_editor_creation(playlist_editor):
    assert playlist_editor is not None
    assert "Playlist Editor" in playlist_editor.windowTitle()

def test_playlist_editor_buttons(playlist_editor):
    assert playlist_editor.new_button is not None
    assert isinstance(playlist_editor.new_button, QPushButton)
    assert playlist_editor.load_button is not None
    assert playlist_editor.save_button is not None
    assert playlist_editor.save_as_button is not None
    assert playlist_editor.done_button is not None

# --- NEW TEST: Test loading with the new helper ---
@patch('myapp.gui.playlist_editor.get_themed_open_filename')
@patch('myapp.gui.playlist_editor.QMessageBox.question', return_value=QMessageBox.StandardButton.Discard)
def test_load_playlist_dialog_calls_helper(mock_discard, mock_get_themed, playlist_editor):
    """Tests if load_playlist_dialog calls the new helper function."""
    dummy_file = "my_playlist.json"
    mock_get_themed.return_value = dummy_file
    with patch.object(playlist_editor.playlist, 'load') as mock_load:
        playlist_editor.load_playlist_dialog()
        mock_get_themed.assert_called_once_with(
            playlist_editor, "Load Playlist", playlist_editor.playlists_base_dir, "JSON Files (*.json)"
        )
        mock_load.assert_called_once_with(dummy_file)
# --- END NEW TEST ---

# --- NEW TEST: Test saving as with the new helper ---
@patch('myapp.gui.playlist_editor.get_themed_save_filename')
@patch('myapp.gui.playlist_editor.is_safe_filename_component', return_value=True)
@patch('myapp.gui.playlist_editor.os.path.exists', return_value=False)
@patch.object(Playlist, 'save', return_value=True)
@patch('myapp.gui.playlist_editor.QMessageBox.information')
def test_save_playlist_as_calls_helper(mock_info, mock_save, mock_exists, mock_safe, mock_get_themed, playlist_editor):
    """Tests if save_playlist_as calls the new helper and saves."""
    save_path = os.path.join(playlist_editor.playlists_base_dir, "new_playlist.json")
    mock_get_themed.return_value = save_path

    # Mock os.path.dirname to ensure it returns the base dir for the check
    with patch('myapp.gui.playlist_editor.os.path.dirname', return_value=playlist_editor.playlists_base_dir):
        result = playlist_editor.save_playlist_as()

    assert result is True
    mock_get_themed.assert_called_once_with(
         playlist_editor, "Save Playlist As", playlist_editor.playlists_base_dir, "JSON Files (*.json)"
    )
    mock_safe.assert_called_once_with("new_playlist.json")
    mock_exists.assert_called_once_with(save_path)
    mock_save.assert_called_once_with(save_path)
    mock_info.assert_called_once()
# --- END NEW TEST ---