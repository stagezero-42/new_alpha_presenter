# tests/test_gui/test_layer_editor_dialog.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from myapp.gui.layer_editor_dialog import LayerEditorDialog

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

@pytest.fixture
def layer_editor(qapp, tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    dialog = LayerEditorDialog([], media_dir, MagicMock())
    return dialog

def test_layer_editor_creation(layer_editor):
    assert layer_editor is not None
    assert layer_editor.windowTitle() == "Edit Slide Layers"

@patch('PySide6.QtWidgets.QFileDialog.getOpenFileNames')
def test_add_layers_copies_files(mock_get_open_file_names, layer_editor, tmp_path):
    source_file = tmp_path / "test_image.png"
    source_file.touch()
    mock_get_open_file_names.return_value = ([str(source_file)], "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)")

    layer_editor.add_layers()

    assert os.path.exists(os.path.join(layer_editor.media_dir, "test_image.png"))
    assert "test_image.png" in layer_editor.slide_layers