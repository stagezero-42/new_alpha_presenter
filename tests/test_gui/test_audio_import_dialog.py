# tests/test_gui/test_audio_import_dialog.py
import pytest
import os
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMessageBox

# Ensure the myapp structure can be imported
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.audio_import_dialog import AudioImportDialog
from myapp.audio.audio_track_manager import AudioTrackManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_audio_track_manager():
    manager = MagicMock(spec=AudioTrackManager)
    manager.list_audio_tracks.return_value = []
    manager.save_track_metadata.return_value = True
    manager.detect_audio_duration.return_value = 120000  # 2 mins
    return manager


@pytest.fixture
def audio_import_dialog(qapp, mock_audio_track_manager, tmp_path):
    # Mock paths used by the dialog
    with patch('myapp.utils.paths.get_media_path', return_value=str(tmp_path / "media")):
        with patch('myapp.utils.paths.get_icon_file_path', return_value="dummy_icon.png"):
            with patch('myapp.gui.widget_helpers.QIcon'):  # Mock QIcon if it causes issues
                dialog = AudioImportDialog(parent=None, audio_track_manager=mock_audio_track_manager)
    return dialog


def test_audio_import_dialog_creation(audio_import_dialog):
    assert audio_import_dialog is not None
    assert "Import Audio File" in audio_import_dialog.windowTitle()
    assert audio_import_dialog.track_name_edit is not None
    assert audio_import_dialog.file_path_edit is not None


@patch('PySide6.QtWidgets.QFileDialog.getOpenFileName')
def test_browse_file_updates_ui(mock_get_open_filename, audio_import_dialog, tmp_path):
    dummy_audio_path = str(tmp_path / "test_song.mp3")
    open(dummy_audio_path, "w").write("dummy")  # create file
    mock_get_open_filename.return_value = (dummy_audio_path, "Audio Files (*.mp3)")

    audio_import_dialog._browse_file()

    assert audio_import_dialog.file_path_edit.text() == dummy_audio_path
    assert audio_import_dialog.track_name_edit.text() == "test_song"  # Assuming default naming logic
    assert audio_import_dialog.source_audio_file_path == dummy_audio_path
    assert audio_import_dialog.target_media_filename == "test_song.mp3"


@patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=("", ""))
def test_browse_file_cancelled(mock_get_open_filename, audio_import_dialog):
    initial_path = audio_import_dialog.file_path_edit.text()
    audio_import_dialog._browse_file()
    assert audio_import_dialog.file_path_edit.text() == initial_path  # Should not change


def test_validate_track_name(audio_import_dialog):
    audio_import_dialog.audio_track_manager.list_audio_tracks.return_value = ["existing_track"]

    is_valid, msg = audio_import_dialog._validate_track_name("new_track")
    assert is_valid is True
    assert msg == "new_track"

    is_valid, msg = audio_import_dialog._validate_track_name(" existing track ")  # Should be handled
    assert is_valid is False  # Because "existing_track" is in the list
    assert "already exists" in msg.lower()

    is_valid, msg = audio_import_dialog._validate_track_name("")
    assert is_valid is False
    assert "cannot be empty" in msg.lower()

    is_valid, msg = audio_import_dialog._validate_track_name("../invalid")
    assert is_valid is False
    assert "invalid characters" in msg.lower()

@patch('PySide6.QtWidgets.QMessageBox.information')
@patch('PySide6.QtWidgets.QMessageBox.warning')
@patch('shutil.copy2')
def test_handle_import_successful(mock_copy, mock_msg_warning, mock_msg_information, audio_import_dialog,
                                  tmp_path):  # Add mock_msg_information to args
    source_file = tmp_path / "source_audio.mp3"
    source_file.touch()

    audio_import_dialog.source_audio_file_path = str(source_file)
    audio_import_dialog.target_media_filename = "source_audio.mp3"
    audio_import_dialog.track_name_edit.setText("imported_track")

    media_dir_path = tmp_path / "media"
    # The get_media_path in the audio_import_dialog fixture is already patched
    # to return tmp_path / "media". Ensure this directory actually exists.
    os.makedirs(media_dir_path, exist_ok=True)

    with patch.object(audio_import_dialog, 'accept') as mock_accept:
        audio_import_dialog._handle_import()

        mock_copy.assert_called_once()
        audio_import_dialog.audio_track_manager.detect_audio_duration.assert_called_once()
        audio_import_dialog.audio_track_manager.save_track_metadata.assert_called_once_with(
            "imported_track",
            {
                "track_name": "imported_track",
                "file_path": "source_audio.mp3",
                "detected_duration_ms": 120000
            }
        )
        mock_accept.assert_called_once()
        mock_msg_warning.assert_not_called()
        mock_msg_information.assert_called_once_with(  # Optionally assert it was called
            audio_import_dialog,
            "Import Successful",
            "Audio track 'imported_track' metadata created."
        )


@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_handle_import_no_file_selected(mock_msg_warning, audio_import_dialog):
    audio_import_dialog.source_audio_file_path = ""
    audio_import_dialog._handle_import()
    mock_msg_warning.assert_called_once_with(audio_import_dialog, "No File", "Please select an audio file to import.")

# Add tests for invalid track name during import, copy error, save metadata error, etc.