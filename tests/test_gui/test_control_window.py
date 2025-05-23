# tests/test_gui/test_control_window.py
# IMPORTANT: Ensure the NameError: name 'Qt' is not defined in myapp/gui/control_window.py is resolved
# by adding 'from PySide6.QtCore import Qt'.

import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap  # For creating dummy images in fixture

# Ensure the myapp directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.control_window import ControlWindow
from myapp.gui.display_window import DisplayWindow  # For spec in mock


# --- Test Fixtures ---
@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication instance for all tests that need it."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_display_window():
    """Mocks the DisplayWindow instance."""
    mock = MagicMock(spec=DisplayWindow)
    mock.display_images = MagicMock()
    mock.clear_display = MagicMock()
    return mock


@pytest.fixture
def test_media_path(tmp_path):
    """
    Creates a temporary directory for test media files for this test session.
    Using pytest's tmp_path fixture for cleaner test-specific directories.
    """
    test_files_dir = tmp_path / "media_files_for_testing"
    test_files_dir.mkdir(exist_ok=True)  # Ensure it exists
    return str(test_files_dir)


@pytest.fixture
def control_window(qapp, mock_display_window, test_media_path):
    """
    Fixture to create a ControlWindow instance with a mocked DisplayWindow.
    Initializes media_files_path to the temporary test_media_path.
    """
    with patch.object(ControlWindow, '_load_playlist_from_path') as mock_fixture_initial_load:
        window = ControlWindow(mock_display_window)

    window.playlist = []
    window.current_index = -1
    # Initialize media_files_path to the temporary test directory for consistent testing
    window.media_files_path = test_media_path

    mock_display_window.reset_mock()
    return window


@pytest.fixture
def valid_playlist_path(test_media_path):
    """Path to a valid test_playlist.json, created in the test_media_path."""
    playlist_file_path = os.path.join(test_media_path, "test_playlist.json")

    playlist_content = {
        "slides": [
            {"comment": "Slide 1: Two valid images", "layers": ["dummy_image1.png", "dummy_image2.png"]},
            {"comment": "Slide 2: One valid image, one missing", "layers": ["dummy_image1.png", "missing_image.png"]},
            {"comment": "Slide 3: One valid image, one non-image file",
             "layers": ["dummy_image2.png", "non_image_file.txt"]},
            {"comment": "Slide 4: Only one valid image", "layers": ["dummy_image1.png"]},
            {"comment": "Slide 5: No images", "layers": []}
        ]
    }
    with open(playlist_file_path, 'w', encoding='utf-8') as f:
        json.dump(playlist_content, f)

    dummy_image1_path = os.path.join(test_media_path, "dummy_image1.png")
    dummy_image2_path = os.path.join(test_media_path, "dummy_image2.png")
    dummy_text_file_path = os.path.join(test_media_path, "non_image_file.txt")

    if not os.path.exists(dummy_image1_path): QPixmap(1, 1).save(dummy_image1_path, "PNG")
    if not os.path.exists(dummy_image2_path): QPixmap(1, 1).save(dummy_image2_path, "PNG")
    if not os.path.exists(dummy_text_file_path):
        with open(dummy_text_file_path, 'w') as f: f.write("dummy text for non_image_file.txt")

    return playlist_file_path


@pytest.fixture
def empty_playlist_content():
    return {"slides": []}


@pytest.fixture
def malformed_playlist_content():
    return "{slides: [}}"  # Invalid JSON string


# --- Test Cases ---

def test_control_window_creation(control_window, mock_display_window):
    assert control_window is not None
    assert control_window.display_window == mock_display_window
    assert control_window.windowTitle() == "Control Window"


@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_load_valid_playlist(mock_msgbox_warning, control_window, mock_display_window, valid_playlist_path,
                             test_media_path):
    # _load_playlist_from_path uses self.media_files_path (set by fixture to test_media_path)
    # if it doesn't update it itself.
    # The key is that after this call, self.media_files_path should be os.path.dirname(valid_playlist_path)
    # IF _load_playlist_from_path was designed to update it. Since it likely isn't (only load_playlist_dialog does),
    # the media_base_path used by update_display will be the one from the fixture (test_media_path).
    # However, for images within 'valid_playlist_path', their base *should* be os.path.dirname(valid_playlist_path).
    # This highlights a potential design consideration in ControlWindow.
    # For this test to pass with current ControlWindow logic:
    # We assume _load_playlist_from_path loads the playlist data, and update_display uses
    # control_window.media_files_path (which is test_media_path from fixture) as base.
    # The playlist image paths are relative to os.path.dirname(valid_playlist_path).
    # This means display_images will be called with (layers, test_media_path)
    # and display_window will try to join test_media_path with layer paths.
    # This is correct if the playlist file itself is IN test_media_path.

    # To make the test reflect that images are relative to the playlist's location:
    # We must ensure control_window.media_files_path is set to the playlist's directory
    # *before* update_display is called by _load_playlist_from_path, or that
    # _load_playlist_from_path itself sets it.
    # Let's assume _load_playlist_from_path does NOT set it.
    # The call to display_images will use control_window.media_files_path (which is test_media_path).
    # The `valid_playlist_path` is inside `test_media_path`. So images are relative to `test_media_path`.

    control_window.media_files_path = os.path.dirname(
        valid_playlist_path)  # Explicitly set for this direct call scenario
    control_window._load_playlist_from_path(valid_playlist_path)

    assert len(control_window.playlist) == 5
    assert control_window.current_index == 0
    expected_layers_slide0 = ["dummy_image1.png", "dummy_image2.png"]
    # The media_base_path passed to display_images should be the directory of the loaded playlist
    expected_media_base_path = os.path.dirname(valid_playlist_path)
    mock_display_window.display_images.assert_called_once_with(expected_layers_slide0, expected_media_base_path)
    mock_msgbox_warning.assert_not_called()


@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_load_missing_playlist(mock_msgbox_warning, control_window, mock_display_window, test_media_path):
    # control_window.media_files_path is test_media_path from fixture
    missing_path_in_temp = os.path.join(test_media_path, "non_existent_playlist.json")
    control_window._load_playlist_from_path(missing_path_in_temp)

    assert len(control_window.playlist) == 0
    assert control_window.current_index == -1
    mock_display_window.clear_display.assert_called_once()
    mock_msgbox_warning.assert_called_once_with(control_window, "Error",
                                                f"Playlist file not found: {missing_path_in_temp}")


@patch('PySide6.QtWidgets.QMessageBox.critical')
def test_load_malformed_playlist(mock_msgbox_critical, control_window, mock_display_window, test_media_path,
                                 malformed_playlist_content):
    malformed_path = os.path.join(test_media_path, "malformed.json")
    with open(malformed_path, 'w') as f:
        f.write(malformed_playlist_content)

        # If _load_playlist_from_path is called, it will use current control_window.media_files_path
    # which is test_media_path. This is fine.
    control_window.media_files_path = os.path.dirname(malformed_path)  # Set context for this load
    control_window._load_playlist_from_path(malformed_path)

    assert len(control_window.playlist) == 0
    assert control_window.current_index == -1
    mock_display_window.clear_display.assert_called_once()
    mock_msgbox_critical.assert_called_once()
    args, _ = mock_msgbox_critical.call_args
    assert args[0] == control_window
    assert args[1] == "Error"
    assert f"Failed to load or parse playlist: {malformed_path}" in args[2]

    os.remove(malformed_path)


@patch('PySide6.QtWidgets.QMessageBox.information')
def test_load_playlist_with_no_slides(mock_msgbox_info, control_window, mock_display_window, test_media_path,
                                      empty_playlist_content):
    empty_slides_path = os.path.join(test_media_path, "empty_slides.json")
    with open(empty_slides_path, 'w', encoding='utf-8') as f:
        json.dump(empty_playlist_content, f)

    control_window.media_files_path = os.path.dirname(empty_slides_path)  # Set context
    control_window._load_playlist_from_path(empty_slides_path)

    assert len(control_window.playlist) == 0
    assert control_window.current_index == -1
    mock_display_window.clear_display.assert_called_once()
    mock_msgbox_info.assert_called_once_with(control_window, "Playlist Empty",
                                             "The loaded playlist contains no slides.")

    os.remove(empty_slides_path)


def test_next_slide_navigation(control_window, mock_display_window, valid_playlist_path, test_media_path):
    # Set media_files_path to the directory of the playlist being loaded for this test
    control_window.media_files_path = os.path.dirname(valid_playlist_path)
    control_window._load_playlist_from_path(valid_playlist_path)
    mock_display_window.display_images.reset_mock()

    control_window.next_slide()  # To slide 1
    assert control_window.current_index == 1
    expected_layers_slide1 = ["dummy_image1.png", "missing_image.png"]
    # media_base_path should be the directory of the currently loaded playlist
    expected_media_base_path = os.path.dirname(valid_playlist_path)
    mock_display_window.display_images.assert_called_with(expected_layers_slide1, expected_media_base_path)

    control_window.next_slide()  # To slide 2
    assert control_window.current_index == 2
    expected_layers_slide2 = ["dummy_image2.png", "non_image_file.txt"]
    mock_display_window.display_images.assert_called_with(expected_layers_slide2, expected_media_base_path)

    control_window.current_index = 3
    control_window.next_slide()
    assert control_window.current_index == 4

    mock_display_window.display_images.reset_mock()
    control_window.next_slide()
    assert control_window.current_index == 4
    mock_display_window.display_images.assert_not_called()


def test_prev_slide_navigation(control_window, mock_display_window, valid_playlist_path, test_media_path):
    control_window.media_files_path = os.path.dirname(valid_playlist_path)
    control_window._load_playlist_from_path(valid_playlist_path)
    control_window.current_index = 2
    mock_display_window.display_images.reset_mock()

    control_window.prev_slide()
    assert control_window.current_index == 1
    expected_layers_slide1 = ["dummy_image1.png", "missing_image.png"]
    expected_media_base_path = os.path.dirname(valid_playlist_path)
    mock_display_window.display_images.assert_called_with(expected_layers_slide1, expected_media_base_path)

    control_window.prev_slide()
    assert control_window.current_index == 0
    expected_layers_slide0 = ["dummy_image1.png", "dummy_image2.png"]
    mock_display_window.display_images.assert_called_with(expected_layers_slide0, expected_media_base_path)

    mock_display_window.display_images.reset_mock()
    control_window.prev_slide()
    assert control_window.current_index == 0
    mock_display_window.display_images.assert_not_called()


@patch('PySide6.QtWidgets.QFileDialog.getOpenFileName')
def test_load_playlist_dialog_opens_and_loads(mock_get_open_file_name, control_window, valid_playlist_path,
                                              mock_display_window, test_media_path):
    # control_window.media_files_path is test_media_path (from fixture) before dialog
    initial_dialog_path = test_media_path
    control_window.media_files_path = initial_dialog_path  # Ensure it's set to what dialog will use

    mock_get_open_file_name.return_value = (valid_playlist_path, "JSON Files (*.json)")

    with patch.object(control_window, '_load_playlist_from_path') as mock_internal_load:
        control_window.load_playlist_dialog()  # This will call QFileDialog and then _load_playlist_from_path

        mock_get_open_file_name.assert_called_once()
        args_call, _ = mock_get_open_file_name.call_args
        assert args_call[2] == initial_dialog_path  # default_dir argument should be the initial media_files_path

        # load_playlist_dialog updates self.media_files_path BEFORE calling _load_playlist_from_path
        # So, _load_playlist_from_path is called in the context of the new path.
        # mock_internal_load is called with valid_playlist_path.
        # Inside _load_playlist_from_path, update_display will use the *updated* self.media_files_path.
        mock_internal_load.assert_called_once_with(valid_playlist_path)

    # After load_playlist_dialog, control_window.media_files_path should be the dir of valid_playlist_path
    assert control_window.media_files_path == os.path.dirname(valid_playlist_path)

    # If _load_playlist_from_path (mocked here) were to call display_images,
    # it would use os.path.dirname(valid_playlist_path) because load_playlist_dialog updated it.
    # To test the call to display_images, we'd need to not mock _load_playlist_from_path fully,
    # or check its call to update_display, which then calls display_images.
    # For this test, we focus on dialog interaction and path update.
    # A separate test could verify the full chain if _load_playlist_from_path wasn't mocked.


@patch('PySide6.QtWidgets.QFileDialog.getOpenFileName')
def test_load_playlist_dialog_cancel(mock_get_open_file_name, control_window, test_media_path):
    initial_media_path = test_media_path  # Path set by fixture
    control_window.media_files_path = initial_media_path  # Ensure this is the path before dialog

    mock_get_open_file_name.return_value = ("", "")

    with patch.object(control_window, '_load_playlist_from_path') as mock_internal_load:
        control_window.load_playlist_dialog()
        mock_get_open_file_name.assert_called_once()
        mock_internal_load.assert_not_called()
        assert control_window.media_files_path == initial_media_path
