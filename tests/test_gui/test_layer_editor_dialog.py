# tests/test_gui/test_layer_editor_dialog.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

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

    with patch('myapp.gui.layer_editor_dialog.get_media_path', return_value=str(media_dir)):
        with patch('myapp.gui.layer_editor_dialog.get_icon_file_path', return_value="dummy_icon.png"):
            dialog = LayerEditorDialog([], 0, 0, MagicMock(), None)
    return dialog


def test_layer_editor_creation(layer_editor):
    assert layer_editor is not None
    assert layer_editor.windowTitle() == "Edit Slide Details"  # Updated title


@patch('PySide6.QtWidgets.QFileDialog.getOpenFileNames')
def test_add_layers_copies_files(mock_get_open_file_names, layer_editor, tmp_path):
    source_file = tmp_path / "test_image.png"
    source_file.touch()
    mock_get_open_file_names.return_value = ([str(source_file)], "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)")

    layer_editor.add_layers()

    assert os.path.exists(os.path.join(layer_editor.media_path, "test_image.png"))
    assert "test_image.png" in layer_editor.slide_layers


def test_get_updated_slide_data(layer_editor):
    """Test if the dialog correctly returns layers, duration, and loop target."""
    # Simulate user input
    expected_layers = ["image1.png", "image2.png"]
    expected_duration = 10
    expected_loop_target = 2

    # 1. Set the internal list that populate_layers_list will use
    layer_editor.slide_layers = list(expected_layers)
    # --- MODIFIED: Call populate_layers_list to update the QListWidget ---
    layer_editor.populate_layers_list()
    # --- END MODIFIED ---

    layer_editor.duration_spinbox.setValue(expected_duration)
    layer_editor.loop_target_spinbox.setValue(expected_loop_target)

    # Now, update_internal_layers_from_widget will read from the populated QListWidget
    # This simulates what happens when accept_changes() is called before get_updated_slide_data()
    layer_editor.update_internal_layers_from_widget()

    updated_data = layer_editor.get_updated_slide_data()

    assert updated_data["layers"] == expected_layers
    assert updated_data["duration"] == expected_duration
    assert updated_data["loop_to_slide"] == expected_loop_target