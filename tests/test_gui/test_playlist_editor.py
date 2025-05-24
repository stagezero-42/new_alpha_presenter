# tests/test_gui/test_playlist_editor.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from myapp.gui.playlist_editor import PlaylistEditorWindow
from myapp.playlist.playlist import Playlist

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

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
def playlist_editor(qapp, mock_display_window):
    playlist = Playlist()
    window = PlaylistEditorWindow(mock_display_window, playlist)
    return window

def test_playlist_editor_creation(playlist_editor):
    assert playlist_editor is not None
    assert playlist_editor.windowTitle() == "Playlist Editor - Untitled [*]"

def test_add_slide_opens_layer_editor(playlist_editor):
    with patch.object(playlist_editor, 'edit_selected_slide_layers') as mock_edit_layers:
        playlist_editor.add_slide()
        mock_edit_layers.assert_called_once()