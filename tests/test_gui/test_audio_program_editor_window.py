# tests/test_gui/test_audio_program_editor_window.py
import pytest
import os
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import QUrl
from pathlib import Path  # Ensure pathlib is imported

# Ensure the myapp structure can be imported
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.audio_program_editor_window import AudioProgramEditorWindow
from myapp.audio.audio_program_manager import AudioProgramManager
from myapp.audio.audio_track_manager import AudioTrackManager
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_program_manager():
    manager = MagicMock(spec=AudioProgramManager)
    manager.list_programs.return_value = ["program1", "program2"]
    manager.load_program.side_effect = lambda name: {"program_name": name, "tracks": [], "loop_indefinitely": False,
                                                     "loop_count": 0} if name in ["program1",
                                                                                  "program2"] else FileNotFoundError
    manager.save_program.return_value = True
    manager.delete_program.return_value = True
    return manager


@pytest.fixture
def mock_track_manager():
    manager = MagicMock(spec=AudioTrackManager)
    manager.list_audio_tracks.return_value = ["track_meta1", "track_meta2"]
    manager.load_track_metadata.side_effect = lambda name: {"track_name": name, "file_path": f"{name}.mp3",
                                                            "detected_duration_ms": 180000} if name in ["track_meta1",
                                                                                                        "track_meta2"] else FileNotFoundError
    return manager


@pytest.fixture
def audio_program_editor(qapp, mock_program_manager, mock_track_manager, tmp_path, mocker):  # Add mocker
    dummy_icon_file = tmp_path / "dummy_icon.png"
    if not dummy_icon_file.exists():
        dummy_icon_file.touch()

    media_dir = tmp_path / "media"
    os.makedirs(media_dir, exist_ok=True)

    # 1. Patch dependencies of AudioProgramEditorWindow module FIRST
    #    These are an absolute priority before the module itself is imported.
    mocker.patch('myapp.gui.audio_program_editor_window.AudioProgramManager', return_value=mock_program_manager)
    mocker.patch('myapp.gui.audio_program_editor_window.AudioTrackManager', return_value=mock_track_manager)
    mocker.patch('myapp.gui.audio_program_editor_window.get_icon_file_path', return_value=str(dummy_icon_file))
    # THIS IS THE CRITICAL PATCH - applied before AudioProgramEditorWindow is imported by the fixture
    mocked_get_media_file_path = mocker.patch('myapp.gui.audio_program_editor_window.get_media_file_path',
                                              side_effect=lambda x: str(media_dir / x))

    # Patch QMediaPlayer methods that will be used by the instance.
    # These are patched on the class, so new instances will use these mocks.
    mocker.patch.object(QMediaPlayer, 'setAudioOutput')
    mocker.patch.object(QMediaPlayer, 'play')
    mocker.patch.object(QMediaPlayer, 'pause')
    mocker.patch.object(QMediaPlayer, 'stop')
    mocker.patch.object(QMediaPlayer, 'setSource')  # General mock for setSource
    mocker.patch.object(QMediaPlayer, 'position', return_value=0)
    mocker.patch.object(QMediaPlayer, 'duration', return_value=0)
    mocker.patch.object(QMediaPlayer, 'mediaStatus', return_value=QMediaPlayer.MediaStatus.NoMedia)
    mocker.patch.object(QMediaPlayer, 'playbackState', return_value=QMediaPlayer.PlaybackState.StoppedState)
    mocker.patch.object(QMediaPlayer, 'errorString', return_value="")
    mocker.patch.object(QMediaPlayer, 'error',
                        return_value=QMediaPlayer.Error.NoError)  # PySide6.QtMultimedia.QMediaPlayer.Error.NoError
    mocker.patch.object(QAudioOutput, 'setVolume')

    # Now import the class anD instantiate it
    from myapp.gui.audio_program_editor_window import AudioProgramEditorWindow
    editor = AudioProgramEditorWindow(parent=None)

    # For debugging the patch:
    # print(f"DEBUG Fixture: mocked_get_media_file_path is {mocked_get_media_file_path}")
    # print(f"DEBUG Fixture: editor.get_media_file_path('test.mp3') would call: {editor.get_media_file_path('test.mp3') if hasattr(editor, 'get_media_file_path') else 'N/A on editor'}")
    # print(f"DEBUG Fixture: Actual get_media_file_path in module: {AudioProgramEditorWindow.get_media_file_path('test.mp3')}")

    return editor


def test_editor_creation_and_program_listing(audio_program_editor, mock_program_manager):
    assert audio_program_editor is not None
    assert "Audio Program Editor" in audio_program_editor.windowTitle()
    mock_program_manager.list_programs.assert_called_once()
    assert audio_program_editor.program_list_widget.count() == 2


@patch('PySide6.QtWidgets.QInputDialog.getText', return_value=("new_program", True))
def test_add_program(mock_input_dialog, audio_program_editor, mock_program_manager):
    audio_program_editor.add_program()
    mock_program_manager.save_program.assert_called_with(
        "new_program",
        {"program_name": "new_program", "tracks": [], "loop_indefinitely": False, "loop_count": 0}
    )


@patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=("track_meta1", True))
def test_add_track_to_program(mock_input_dialog, audio_program_editor, mock_program_manager):
    audio_program_editor.program_list_widget.setCurrentRow(0)
    with patch.object(audio_program_editor.track_in_program_manager, 'add_track_to_program') as mock_add_track_method:
        audio_program_editor.add_track_to_program()
        mock_add_track_method.assert_called_once_with("track_meta1")


def test_select_track_updates_player_ui(audio_program_editor, mock_program_manager, mock_track_manager, tmp_path,
                                        mocker):
    program_name = "program_with_track"
    track_meta_name = "track_meta1"
    dummy_media_file_name = f"{track_meta_name}.mp3"

    media_dir_from_fixture = tmp_path / "media"
    dummy_media_full_path = media_dir_from_fixture / dummy_media_file_name
    if not dummy_media_full_path.exists():
        dummy_media_full_path.touch()

    program_data_for_test = {
        "program_name": program_name,
        "tracks": [{"track_name": track_meta_name, "play_order": 0, "user_start_time_ms": 0, "user_end_time_ms": None}],
        "loop_indefinitely": False, "loop_count": 0
    }
    audio_program_editor.programs_cache[program_name] = program_data_for_test

    original_list_programs = list(mock_program_manager.list_programs.return_value)
    if program_name not in original_list_programs:
        mock_program_manager.list_programs.return_value = original_list_programs + [program_name]

    original_load_program_side_effect = mock_program_manager.load_program.side_effect

    def new_load_program_side_effect(name_to_load):
        if name_to_load == program_name:
            return program_data_for_test
        if callable(original_load_program_side_effect):
            try:
                return original_load_program_side_effect(name_to_load)
            except FileNotFoundError:
                pass
        if name_to_load in audio_program_editor.programs_cache:
            return audio_program_editor.programs_cache[name_to_load]
        raise FileNotFoundError(f"Test Mock: Program {name_to_load} not found by new_load_program_side_effect")

    mock_program_manager.load_program.side_effect = new_load_program_side_effect

    mock_set_source_on_instance = mocker.patch.object(audio_program_editor.media_player, 'setSource')

    audio_program_editor._refresh_and_select_program(program_name)

    assert audio_program_editor.tracks_table_widget.rowCount() > 0, \
        f"Track table is empty. Program: '{program_name}', Data in manager: {audio_program_editor.track_in_program_manager.current_program_data}"

    # This should trigger the connected slot (handle_track_selection_changed in AudioTrackInProgramManager)
    audio_program_editor.tracks_table_widget.selectRow(0)

    # REMOVED: audio_program_editor.track_in_program_manager.handle_track_selection_changed()

    # If signals are not processed immediately in the test environment,
    # you might need qtbot to wait for signals or process events.
    # For now, let's assume selectRow() is enough to trigger the chain.
    # If it still fails with "Called 0 times", this part needs qtbot.

    expected_qurl = QUrl.fromLocalFile(str(dummy_media_full_path))
    try:
        mock_set_source_on_instance.assert_called_once_with(expected_qurl)
    except AssertionError as e:
        print(f"Calls to mock_set_source_instance: {mock_set_source_on_instance.call_args_list}")
        raise e

    assert audio_program_editor.loaded_track_label.text().startswith("Loading:") or \
           audio_program_editor.loaded_track_label.text().startswith("Ready:")

    mock_program_manager.list_programs.return_value = original_list_programs
    mock_program_manager.load_program.side_effect = original_load_program_side_effect