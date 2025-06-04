# tests/test_gui/test_audio_import_dialog.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QUrl

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from myapp.gui.audio_import_dialog import AudioImportDialog
from myapp.audio.audio_track_manager import AudioTrackManager  # For spec


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_audio_track_manager():
    manager = MagicMock(spec=AudioTrackManager)
    manager.list_audio_tracks.return_value = ["existing_track"]

    mock_successful_metadata = {
        "track_name": "newly_imported_track",
        "file_path": "newly_imported_file.mp3",
        "detected_duration_ms": 123000
    }
    manager.create_metadata_from_file.return_value = (mock_successful_metadata, None)
    return manager


@pytest.fixture
def dialog(qapp, mock_audio_track_manager):
    with patch('myapp.gui.widget_helpers.get_icon_file_path', return_value="dummy_icon.png"):
        # Patch QIcon directly in the audio_import_dialog module for the test
        with patch('myapp.gui.audio_import_dialog.QIcon', MagicMock()):
            dlg = AudioImportDialog(parent=None, track_manager=mock_audio_track_manager)
    return dlg


def test_audio_import_dialog_creation(dialog):
    assert dialog.windowTitle() == "Import Audio Track"
    assert dialog.track_name_edit.text() == ""
    assert dialog.file_path_label.text() == "No file selected."


@patch('myapp.gui.audio_import_dialog.get_themed_open_filename')
def test_browse_file_updates_ui(mock_get_open_filename, dialog, tmp_path):
    test_file_path = tmp_path / "test_audio.mp3"
    test_file_path.touch()
    mock_get_open_filename.return_value = str(test_file_path)

    dialog.browse_file()

    assert dialog.selected_file_path == str(test_file_path)
    assert dialog.file_path_label.text() == str(test_file_path)
    assert dialog.track_name_edit.text() == "test_audio"
    mock_get_open_filename.assert_called_once()


@patch('myapp.gui.audio_import_dialog.get_themed_open_filename')
def test_browse_file_cancelled(mock_get_open_filename, dialog):
    mock_get_open_filename.return_value = ""
    dialog.browse_file()
    assert dialog.selected_file_path == ""
    assert dialog.file_path_label.text() == "No file selected."
    assert dialog.track_name_edit.text() == ""


def test_validate_track_name(dialog, mock_audio_track_manager):
    # Valid name
    dialog.track_name_edit.setText("new_track")
    assert dialog.validate_track_name()

    # Empty name
    dialog.track_name_edit.setText("")
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_msgbox:
        assert not dialog.validate_track_name()
        mock_msgbox.assert_called_once_with(dialog, "Invalid Name", "Track name cannot be empty.")

    # Existing name
    existing_name_to_test = "existing_track"
    dialog.track_name_edit.setText(existing_name_to_test)
    # Ensure the mock list_audio_tracks contains this name for the test
    mock_audio_track_manager.list_audio_tracks.return_value = [existing_name_to_test]
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_msgbox:
        assert not dialog.validate_track_name()
        # Corrected assertion to match the f-string in the actual code
        expected_message = f"A track with the name '{existing_name_to_test}' already exists."
        mock_msgbox.assert_called_once_with(dialog, "Name Exists", expected_message)

    # Unsafe name
    dialog.track_name_edit.setText("../unsafe")
    # Reset list_audio_tracks for this part of the test if needed, or ensure it doesn't interfere
    mock_audio_track_manager.list_audio_tracks.return_value = []
    with patch('myapp.gui.audio_import_dialog.is_safe_filename_component', return_value=False):
        with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_msgbox:
            assert not dialog.validate_track_name()
            # Check that the specific warning for unsafe characters is called
            mock_msgbox.assert_called_once_with(dialog, "Invalid Name",
                                                "Track name '../unsafe' contains invalid characters or is a reserved name.")


@patch('PySide6.QtWidgets.QMessageBox.information')
def test_handle_import_successful(mock_msgbox_info, dialog, mock_audio_track_manager, tmp_path):
    dialog.selected_file_path = str(tmp_path / "audio.mp3")
    (tmp_path / "audio.mp3").touch()
    dialog.track_name_edit.setText("my_new_track")

    mock_successful_metadata = {
        "track_name": "my_new_track",
        "file_path": "audio.mp3",
        "detected_duration_ms": 60000
    }
    mock_audio_track_manager.create_metadata_from_file.return_value = (mock_successful_metadata, None)

    with patch.object(dialog, 'accept') as mock_accept:
        dialog.handle_import()
        mock_audio_track_manager.create_metadata_from_file.assert_called_once_with(
            "my_new_track", str(tmp_path / "audio.mp3")
        )
        mock_msgbox_info.assert_called_once_with(dialog, "Success", "Track 'my_new_track' imported successfully.")
        mock_accept.assert_called_once()


def test_handle_import_no_file_selected(dialog):
    dialog.selected_file_path = ""
    dialog.track_name_edit.setText("my_track")
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_msgbox:
        dialog.handle_import()
        mock_msgbox.assert_called_once_with(dialog, "Missing Information", "Please select an audio file to import.")