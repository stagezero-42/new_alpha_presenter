# tests/test_gui/test_layer_editor_dialog.py
import pytest
import os
import sys
import shutil
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.layer_editor_dialog import LayerEditorDialog
from myapp.text.paragraph_manager import ParagraphManager
# Import defaults to ensure test matches them
from myapp.utils.schemas import (
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_FONT_COLOR,
    DEFAULT_BACKGROUND_COLOR, DEFAULT_TEXT_ALIGN,
    DEFAULT_TEXT_VERTICAL_ALIGN, DEFAULT_FIT_TO_WIDTH
    # DEFAULT_BACKGROUND_ALPHA will be calculated due to slider conversion
)


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

    # current_text_overlay is passed to __init__.
    # If it's a mock, __init__ will treat it as if no prior overlay data was passed,
    # thus using defaults for all style fields when load_text_overlay_ui is called.
    # If it's an empty dict {}, same result.
    initial_text_overlay_for_dialog = {}

    with patch('myapp.utils.paths.get_media_path', return_value=str(media_dir)):
        with patch('myapp.utils.paths.get_media_file_path', lambda x: os.path.join(str(media_dir), x)):
            with patch('myapp.utils.paths.get_icon_file_path', return_value="dummy_icon.png"):
                dialog = LayerEditorDialog(
                    slide_layers=[],
                    current_duration=0,
                    current_loop_target=0,
                    current_text_overlay=initial_text_overlay_for_dialog,  # Pass empty dict
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
def test_add_layers_copies_files(mock_warning, mock_copy, mock_is_safe, mock_get_themed_open_filenames, layer_editor,
                                 tmp_path):
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
def test_add_layers_skips_unsafe_files(mock_warning, mock_copy, mock_is_safe, mock_get_themed_open_filenames,
                                       layer_editor, tmp_path):
    unsafe_filename_as_selected = "/some/path/../unsafe_image.png"

    mock_get_themed_open_filenames.return_value = [unsafe_filename_as_selected]
    mock_is_safe.return_value = False

    layer_editor.add_layers()

    mock_get_themed_open_filenames.assert_called_once_with(
        layer_editor,
        "Select Images",
        layer_editor.media_path,
        "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
    )
    mock_is_safe.assert_called_once_with(os.path.basename(unsafe_filename_as_selected))
    mock_copy.assert_not_called()
    assert os.path.basename(unsafe_filename_as_selected) not in layer_editor.slide_layers
    mock_warning.assert_called_once()


def test_get_updated_slide_data(layer_editor):
    expected_layers = ["image1.png", "image2.png"]
    expected_duration = 10
    expected_loop_target = 2
    expected_paragraph_name = "test_para"

    # Calculate the expected alpha after round trip through slider
    # Default alpha is 150. Slider val = round(9*(1-150/255)) = 4.
    # Alpha from slider val 4 = 255 - (4*25) = 155.
    expected_calculated_alpha = 155

    # This now needs to include all default style fields
    expected_text_overlay = {
        "paragraph_name": expected_paragraph_name,
        "start_sentence": 1,
        "end_sentence": "all",
        "sentence_timing_enabled": True,
        "auto_advance_slide": False,
        # Default style values that will be picked up
        "font_family": DEFAULT_FONT_FAMILY,
        "font_size": DEFAULT_FONT_SIZE,
        "font_color": DEFAULT_FONT_COLOR,
        "background_color": DEFAULT_BACKGROUND_COLOR,
        "background_alpha": expected_calculated_alpha,  # Adjusted for slider conversion
        "text_align": DEFAULT_TEXT_ALIGN,
        "text_vertical_align": DEFAULT_TEXT_VERTICAL_ALIGN,
        "fit_to_width": DEFAULT_FIT_TO_WIDTH
    }

    mock_paragraph_data = {
        "name": expected_paragraph_name,
        "sentences": [
            {"text": "Sentence 1", "delay_seconds": 2.0},
            {"text": "Sentence 2", "delay_seconds": 3.0}
        ]
    }
    with patch.object(layer_editor.paragraph_manager, 'load_paragraph',
                      return_value=mock_paragraph_data) as mock_load_para:
        layer_editor.slide_layers = list(expected_layers)
        layer_editor.populate_layers_list()
        layer_editor.duration_spinbox.setValue(expected_duration)
        layer_editor.loop_target_spinbox.setValue(expected_loop_target)

        if expected_paragraph_name not in layer_editor.available_paragraphs:
            layer_editor.available_paragraphs.append(expected_paragraph_name)
            layer_editor.paragraph_combo.addItem(expected_paragraph_name, expected_paragraph_name)

        # This will trigger load_text_overlay_ui via update_text_fields_state,
        # which sets the UI style elements to their defaults because current_text_overlay was initially empty.
        layer_editor.paragraph_combo.setCurrentText(expected_paragraph_name)
        mock_load_para.assert_called_with(expected_paragraph_name)

        # Set the operational parts of text_overlay
        layer_editor.start_sentence_spinbox.setValue(expected_text_overlay["start_sentence"])
        layer_editor.end_all_checkbox.setChecked(True)  # for "all"
        layer_editor.sentence_timing_check.setChecked(expected_text_overlay["sentence_timing_enabled"])
        layer_editor.auto_advance_slide_check.setChecked(expected_text_overlay["auto_advance_slide"])

        # The style UI elements (font_combo, font_size_spinbox etc.) would have been set
        # to defaults by load_text_overlay_ui when paragraph_combo changed.
        # get_updated_slide_data will read these current UI values.

        updated_data = layer_editor.get_updated_slide_data()

    assert updated_data["layers"] == expected_layers
    assert updated_data["duration"] == expected_duration
    assert updated_data["loop_to_slide"] == expected_loop_target
    assert updated_data["text_overlay"] == expected_text_overlay  # This should now pass