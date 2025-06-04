# tests/test_gui/test_layer_editor_dialog.py
import pytest
import os
import sys
import shutil
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox, \
    QTabWidget

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.layer_editor_dialog import LayerEditorDialog
from myapp.text.paragraph_manager import ParagraphManager
from myapp.audio.audio_program_manager import AudioProgramManager
from myapp.utils.schemas import (
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_FONT_COLOR,
    DEFAULT_BACKGROUND_COLOR, DEFAULT_BACKGROUND_ALPHA,
    DEFAULT_TEXT_ALIGN, DEFAULT_TEXT_VERTICAL_ALIGN, DEFAULT_FIT_TO_WIDTH,
    DEFAULT_AUDIO_PROGRAM_VOLUME
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def layer_editor(qapp, tmp_path, qtbot): # Added qtbot
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    initial_text_overlay_for_dialog = {}
    initial_audio_program_name = None
    dialog_instance = None # Define outside with blocks for access in finally/yield

    try:
        # Mock AudioProgramManager to prevent disk access
        with patch('myapp.gui.layer_editor_dialog.AudioProgramManager') as mock_apm:
            mock_apm.return_value.list_programs.return_value = ["test_program1", "test_program2"]
            with patch('myapp.utils.paths.get_media_path', return_value=str(media_dir)):
                with patch('myapp.utils.paths.get_media_file_path', lambda x: os.path.join(str(media_dir), x)):
                    with patch('myapp.utils.paths.get_icon_file_path', return_value="dummy_icon.png"):
                        dialog_instance = LayerEditorDialog(
                            slide_layers=[],
                            current_duration=0,
                            current_loop_target=0,
                            current_text_overlay=initial_text_overlay_for_dialog,
                            current_audio_program_name=initial_audio_program_name,
                            current_loop_audio_program=False,
                            current_audio_intro_delay_ms=0,
                            current_audio_outro_duration_ms=0,
                            current_audio_program_volume=DEFAULT_AUDIO_PROGRAM_VOLUME,
                            display_window_instance=MagicMock(),
                            parent=None
                        )
        if dialog_instance:
            qtbot.addWidget(dialog_instance) # Register dialog with qtbot

        yield dialog_instance # Provide the dialog to the test

    finally:
        # Teardown: Ensure the dialog is closed
        if dialog_instance and dialog_instance.isVisible():
            # print(f"Closing dialog in fixture teardown: {dialog_instance.windowTitle()}")
            dialog_instance.close()
        elif dialog_instance:
            # If not visible but exists, ensure it's cleaned up if not parented
            # print(f"Dialog existed but was not visible in teardown: {dialog_instance.windowTitle()}")
            # qtbot.addWidget() should handle deletion, but explicit close helps clear resources.
            dialog_instance.close() # Still good practice to call close


def test_layer_editor_creation(layer_editor):
    assert layer_editor is not None
    assert layer_editor.windowTitle() == "Edit Slide Details"
    assert isinstance(layer_editor.details_tab_widget, QTabWidget)
    assert layer_editor.details_tab_widget.count() == 2


@patch('myapp.gui.layer_editor_dialog.get_themed_open_filenames')
@patch('myapp.gui.layer_editor_dialog.is_safe_filename_component', return_value=True)
@patch('shutil.copy2')
@patch('PySide6.QtWidgets.QMessageBox.warning')
def test_add_layers_copies_files(mock_warning, mock_copy, mock_is_safe, mock_get_themed_open_filenames, layer_editor,
                                 tmp_path):
    source_file = tmp_path / "test_image.png"
    source_file.touch()
    mock_get_themed_open_filenames.return_value = [str(source_file)]

    layer_editor.add_layers() # This might show a QFileDialog internally

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
    # This test calls dialog.exec() implicitly if it calls a method that shows the dialog
    # However, the original test_get_updated_slide_data did not show the dialog,
    # it directly manipulated widgets and then called get_updated_slide_data.
    # If any part of these manipulations somehow causes the dialog to be shown (e.g. a QColorDialog),
    # qtbot will manage it.

    expected_layers = ["image1.png", "image2.png"]
    expected_duration = 10
    expected_loop_target = 2
    expected_paragraph_name = "test_para"
    expected_audio_program_name = "test_program1"
    expected_loop_audio_program = True
    expected_audio_intro_delay_ms = 500
    expected_audio_outro_duration_ms = 250
    expected_audio_program_volume = 0.75


    expected_calculated_alpha = 155

    expected_text_overlay = {
        "paragraph_name": expected_paragraph_name,
        "start_sentence": 1,
        "end_sentence": "all",
        "sentence_timing_enabled": True,
        "auto_advance_slide": False,
        "font_family": DEFAULT_FONT_FAMILY,
        "font_size": DEFAULT_FONT_SIZE,
        "font_color": DEFAULT_FONT_COLOR,
        "background_color": DEFAULT_BACKGROUND_COLOR,
        "background_alpha": expected_calculated_alpha,
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
    # Simulate loading data and UI interactions directly on the layer_editor instance
    with patch.object(layer_editor.paragraph_manager, 'load_paragraph',
                      return_value=mock_paragraph_data) as mock_load_para:
        layer_editor.slide_layers = list(expected_layers)
        layer_editor.populate_layers_list() # Updates UI from slide_layers
        layer_editor.duration_spinbox.setValue(expected_duration)
        layer_editor.loop_target_spinbox.setValue(expected_loop_target)

        if expected_paragraph_name not in layer_editor.available_paragraphs:
            layer_editor.available_paragraphs.append(expected_paragraph_name) # Manually update if needed for test
            layer_editor.paragraph_combo.addItem(expected_paragraph_name, expected_paragraph_name)

        # Simulate selecting an audio program and settings
        audio_program_index = layer_editor.audio_program_combo.findData(expected_audio_program_name)
        if audio_program_index != -1:
            layer_editor.audio_program_combo.setCurrentIndex(audio_program_index)
        else:
            layer_editor.audio_program_combo.addItem(expected_audio_program_name, expected_audio_program_name)
            layer_editor.audio_program_combo.setCurrentText(expected_audio_program_name)

        layer_editor.loop_audio_checkbox.setChecked(expected_loop_audio_program)
        layer_editor.audio_intro_delay_spinbox.setValue(expected_audio_intro_delay_ms)
        layer_editor.audio_outro_duration_spinbox.setValue(expected_audio_outro_duration_ms)
        layer_editor.audio_volume_slider.setValue(int(expected_audio_program_volume * 100))

        layer_editor.paragraph_combo.setCurrentText(expected_paragraph_name)

        layer_editor.start_sentence_spinbox.setValue(expected_text_overlay["start_sentence"])
        layer_editor.end_all_checkbox.setChecked(True) # This will disable end_sentence_spinbox
        layer_editor.sentence_timing_check.setChecked(expected_text_overlay["sentence_timing_enabled"])
        layer_editor.auto_advance_slide_check.setChecked(expected_text_overlay["auto_advance_slide"])
        # Font, color, etc., are assumed to be at defaults or need direct setting for test

        updated_data = layer_editor.get_updated_slide_data()

    assert updated_data["layers"] == expected_layers
    assert updated_data["duration"] == expected_duration
    assert updated_data["loop_to_slide"] == expected_loop_target
    assert updated_data["text_overlay"] == expected_text_overlay
    assert updated_data["audio_program_name"] == expected_audio_program_name
    assert updated_data["loop_audio_program"] == expected_loop_audio_program
    assert updated_data["audio_intro_delay_ms"] == expected_audio_intro_delay_ms
    assert updated_data["audio_outro_duration_ms"] == expected_audio_outro_duration_ms
    assert updated_data["audio_program_volume"] == expected_audio_program_volume