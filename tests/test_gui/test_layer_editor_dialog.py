# tests/test_gui/test_layer_editor_dialog.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
# --- MODIFIED: Import QPushButton ---
from PySide6.QtWidgets import QApplication, QPushButton
# --- END MODIFIED ---

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.layer_editor_dialog import LayerEditorDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def layer_editor(qapp, tmp_path):
    """Creates a LayerEditorDialog instance with mocked paths and necessary arguments."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    # --- MODIFIED: Patch sources, DO NOT mock create_button ---
    with patch('myapp.utils.paths.get_media_path', return_value=str(media_dir)):
        with patch('myapp.utils.paths.get_media_file_path', lambda x: os.path.join(str(media_dir), x)):
             # Patch get_icon_file_path at its source
             with patch('myapp.utils.paths.get_icon_file_path', return_value="dummy_icon.png"):
                 # Mock QIcon inside widget_helpers where create_button uses it
                 with patch('myapp.gui.widget_helpers.QIcon'):
                    dialog = LayerEditorDialog([], 0, 0, MagicMock(), None)
    # --- END MODIFIED ---
    return dialog


def test_layer_editor_creation(layer_editor):
    assert layer_editor is not None
    assert layer_editor.windowTitle() == "Edit Slide Details"


@patch('PySide6.QtWidgets.QFileDialog.getOpenFileNames')
@patch('myapp.gui.layer_editor_dialog.is_safe_filename_component', return_value=True)
@patch('shutil.copy2')
@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_add_layers_copies_files(mock_warning, mock_copy, mock_is_safe, mock_get_open_file_names, layer_editor, tmp_path):
    source_file = tmp_path / "test_image.png"
    source_file.touch()
    mock_get_open_file_names.return_value = ([str(source_file)], "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)")

    layer_editor.add_layers()

    mock_is_safe.assert_called_once_with("test_image.png")
    mock_copy.assert_called_once()
    assert "test_image.png" in layer_editor.slide_layers
    mock_warning.assert_not_called()

@patch('PySide6.QtWidgets.QFileDialog.getOpenFileNames')
@patch('myapp.gui.layer_editor_dialog.is_safe_filename_component') # No return_value here
@patch('shutil.copy2')
@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_add_layers_skips_unsafe_files(mock_warning, mock_copy, mock_is_safe, mock_get_open_file_names, layer_editor, tmp_path):
    unsafe_filename = "../unsafe_image.png"
    # Use os.path.abspath to ensure the file is created, even with '..'
    source_file = tmp_path / "test_subdir"
    source_file.mkdir()
    unsafe_file_path = source_file / unsafe_filename
    # We touch it to ensure it exists for QFileDialog mock, though QFileDialog is mocked.
    # It's more about having a plausible input.
    # We must use abspath to create it, but pass the relative one to the mock.
    open(os.path.abspath(unsafe_file_path), 'a').close()

    mock_get_open_file_names.return_value = ([str(unsafe_file_path)], "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)")

    # Set the side effect for the security check
    mock_is_safe.return_value = False

    layer_editor.add_layers()

    # It should check the *basename*
    mock_is_safe.assert_called_once_with("unsafe_image.png")
    mock_copy.assert_not_called()
    assert "unsafe_image.png" not in layer_editor.slide_layers
    mock_warning.assert_called_once()


def test_get_updated_slide_data(layer_editor):
    """Test if the dialog correctly returns layers, duration, and loop target."""
    expected_layers = ["image1.png", "image2.png"]
    expected_duration = 10
    expected_loop_target = 2

    layer_editor.slide_layers = list(expected_layers)
    layer_editor.populate_layers_list()
    layer_editor.duration_spinbox.setValue(expected_duration)
    layer_editor.loop_target_spinbox.setValue(expected_loop_target)
    layer_editor.update_internal_layers_from_widget()

    updated_data = layer_editor.get_updated_slide_data()

    assert updated_data["layers"] == expected_layers
    assert updated_data["duration"] == expected_duration
    assert updated_data["loop_to_slide"] == expected_loop_target