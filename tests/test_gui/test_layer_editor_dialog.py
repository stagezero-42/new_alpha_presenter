# tests/test_gui/test_layer_editor_dialog.py
import pytest
import os
import sys
import shutil
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.layer_editor_dialog import LayerEditorDialog
from myapp.text.paragraph_manager import ParagraphManager # Import for type hinting if needed

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
    mock_text_overlay = MagicMock()

    with patch('myapp.utils.paths.get_media_path', return_value=str(media_dir)):
        with patch('myapp.utils.paths.get_media_file_path', lambda x: os.path.join(str(media_dir), x)):
             # Mock get_icon_file_path to return a string, QIcon will handle it (might be null if file missing, which is fine for test)
             with patch('myapp.utils.paths.get_icon_file_path', return_value="dummy_icon.png"):
                 # REMOVED: with patch('myapp.gui.widget_helpers.QIcon'):
                 dialog = LayerEditorDialog(
                     slide_layers=[],
                     current_duration=0,
                     current_loop_target=0,
                     current_text_overlay=mock_text_overlay,
                     display_window_instance=MagicMock(),
                     parent=None
                 )
    return dialog


def test_layer_editor_creation(layer_editor):
    assert layer_editor is not None
    assert layer_editor.windowTitle() == "Edit Slide Details"

@patch('myapp.gui.layer_editor_dialog.get_themed_open_filenames')
@patch('myapp.gui.layer_editor_dialog.is_safe_filename_component', return_value=True)
@patch('shutil.copy2')
@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_add_layers_copies_files(mock_warning, mock_copy, mock_is_safe, mock_get_themed_open_filenames, layer_editor, tmp_path):
    source_file = tmp_path / "test_image.png"
    source_file.touch()
    mock_get_themed_open_filenames.return_value = [str(source_file)]

    layer_editor.add_layers()

    mock_get_themed_open_filenames.assert_called_once_with(
        layer_editor,
        "Select Images",
        layer_editor.media_path,
        "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
    )
    mock_is_safe.assert_called_once_with("test_image.png")
    mock_copy.assert_called_once()
    assert "test_image.png" in layer_editor.slide_layers
    mock_warning.assert_not_called()

@patch('myapp.gui.layer_editor_dialog.get_themed_open_filenames')
@patch('myapp.gui.layer_editor_dialog.is_safe_filename_component')
@patch('shutil.copy2')
@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_add_layers_skips_unsafe_files(mock_warning, mock_copy, mock_is_safe, mock_get_themed_open_filenames, layer_editor, tmp_path):
    unsafe_filename_as_selected = "/some/path/../unsafe_image.png" # Example of how it might look
    actual_unsafe_basename = "unsafe_image.png" # what os.path.basename would yield

    mock_get_themed_open_filenames.return_value = [unsafe_filename_as_selected]
    mock_is_safe.return_value = False

    layer_editor.add_layers()

    mock_get_themed_open_filenames.assert_called_once_with(
        layer_editor,
        "Select Images",
        layer_editor.media_path,
        "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
    )
    # is_safe_filename_component is called with os.path.basename(unsafe_filename_as_selected)
    mock_is_safe.assert_called_once_with(os.path.basename(unsafe_filename_as_selected))
    mock_copy.assert_not_called()
    assert actual_unsafe_basename not in layer_editor.slide_layers
    mock_warning.assert_called_once()


def test_get_updated_slide_data(layer_editor):
    expected_layers = ["image1.png", "image2.png"]
    expected_duration = 10
    expected_loop_target = 2
    expected_paragraph_name = "test_para"
    expected_text_overlay = {
        "paragraph_name": expected_paragraph_name,
        "start_sentence": 1,
        "end_sentence": "all",
        "sentence_timing_enabled": True,
        "auto_advance_slide": False
    }

    # --- Mock paragraph_manager.load_paragraph ---
    mock_paragraph_data = {
        "name": expected_paragraph_name,
        "sentences": [
            {"text": "Sentence 1", "delay_seconds": 2.0},
            {"text": "Sentence 2", "delay_seconds": 3.0}
        ]
    }
    # Patch the method on the instance of paragraph_manager used by layer_editor
    with patch.object(layer_editor.paragraph_manager, 'load_paragraph', return_value=mock_paragraph_data) as mock_load_para:
        layer_editor.slide_layers = list(expected_layers)
        layer_editor.populate_layers_list() # Should be fine
        layer_editor.duration_spinbox.setValue(expected_duration)
        layer_editor.loop_target_spinbox.setValue(expected_loop_target)

        # Simulate UI interaction for text overlay
        # Ensure "test_para" is in available_paragraphs if your combo box relies on it for finding index
        # or that setCurrentText can handle direct text setting.
        # For simplicity, let's assume setCurrentText works.
        # If available_paragraphs is empty, addItem first
        if expected_paragraph_name not in layer_editor.available_paragraphs:
             layer_editor.available_paragraphs.append(expected_paragraph_name) # Simulate it being listable
             layer_editor.paragraph_combo.addItem(expected_paragraph_name, expected_paragraph_name)


        layer_editor.paragraph_combo.setCurrentText(expected_paragraph_name) # This triggers update_text_fields_state

        # After setCurrentText, load_paragraph should have been called
        mock_load_para.assert_called_with(expected_paragraph_name)

        layer_editor.start_sentence_spinbox.setValue(expected_text_overlay["start_sentence"])
        layer_editor.end_all_checkbox.setChecked(True)
        layer_editor.sentence_timing_check.setChecked(expected_text_overlay["sentence_timing_enabled"])
        layer_editor.auto_advance_slide_check.setChecked(expected_text_overlay["auto_advance_slide"])

        updated_data = layer_editor.get_updated_slide_data()

    assert updated_data["layers"] == expected_layers
    assert updated_data["duration"] == expected_duration
    assert updated_data["loop_to_slide"] == expected_loop_target
    assert updated_data["text_overlay"] == expected_text_overlay