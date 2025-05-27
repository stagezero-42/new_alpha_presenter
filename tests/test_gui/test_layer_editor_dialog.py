# tests/test_gui/test_layer_editor_dialog.py
import pytest
import os
import sys
import shutil # Import shutil
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox # Import QMessageBox

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

    with patch('myapp.utils.paths.get_media_path', return_value=str(media_dir)):
        with patch('myapp.utils.paths.get_media_file_path', lambda x: os.path.join(str(media_dir), x)):
             with patch('myapp.utils.paths.get_icon_file_path', return_value="dummy_icon.png"):
                 with patch('myapp.gui.widget_helpers.QIcon'):
                    dialog = LayerEditorDialog([], 0, 0, MagicMock(), None)
    return dialog


def test_layer_editor_creation(layer_editor):
    assert layer_editor is not None
    assert layer_editor.windowTitle() == "Edit Slide Details"

# --- MODIFIED: Patch new helper 'get_themed_open_filenames' ---
@patch('myapp.gui.layer_editor_dialog.get_themed_open_filenames')
@patch('myapp.gui.layer_editor_dialog.is_safe_filename_component', return_value=True)
@patch('shutil.copy2')
@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_add_layers_copies_files(mock_warning, mock_copy, mock_is_safe, mock_get_themed_open_filenames, layer_editor, tmp_path):
    source_file = tmp_path / "test_image.png"
    source_file.touch()
    # The new helper returns a list of paths
    mock_get_themed_open_filenames.return_value = [str(source_file)]

    layer_editor.add_layers()

    # Assert our new helper was called correctly
    mock_get_themed_open_filenames.assert_called_once_with(
        layer_editor, "Select Image Files to Add as Layers", layer_editor.media_path,
        "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
    )
    mock_is_safe.assert_called_once_with("test_image.png")
    mock_copy.assert_called_once()
    assert "test_image.png" in layer_editor.slide_layers
    mock_warning.assert_not_called()
# --- END MODIFIED ---

# --- MODIFIED: Patch new helper 'get_themed_open_filenames' ---
@patch('myapp.gui.layer_editor_dialog.get_themed_open_filenames')
@patch('myapp.gui.layer_editor_dialog.is_safe_filename_component')
@patch('shutil.copy2')
@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_add_layers_skips_unsafe_files(mock_warning, mock_copy, mock_is_safe, mock_get_themed_open_filenames, layer_editor, tmp_path):
    unsafe_filename = "../unsafe_image.png"
    source_file = tmp_path / "test_subdir"
    source_file.mkdir()
    unsafe_file_path = source_file / unsafe_filename
    open(os.path.abspath(unsafe_file_path), 'a').close()

    # The new helper returns a list of paths
    mock_get_themed_open_filenames.return_value = [str(unsafe_file_path)]
    mock_is_safe.return_value = False

    layer_editor.add_layers()

    mock_get_themed_open_filenames.assert_called_once()
    mock_is_safe.assert_called_once_with("unsafe_image.png")
    mock_copy.assert_not_called()
    assert "unsafe_image.png" not in layer_editor.slide_layers
    mock_warning.assert_called_once()
# --- END MODIFIED ---

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