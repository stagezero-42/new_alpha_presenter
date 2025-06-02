# tests/test_gui/test_audio_program_editor_window.py
import pytest
import os
from unittest.mock import MagicMock, patch, ANY
from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import QUrl
from pathlib import Path

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
    # This list is the source of truth for the mock's state during a test run
    # It's reset for each test that uses this fixture.
    manager._known_programs_list_for_mock = ["program1", "program2"]

    def list_programs_mock_impl():
        # logger.debug(f"MOCK list_programs called, returning: {manager._known_programs_list_for_mock}")
        return list(manager._known_programs_list_for_mock)  # Return a copy

    def load_program_mock_impl(name):
        # logger.debug(f"MOCK load_program called for: {name}, known: {manager._known_programs_list_for_mock}")
        if name in manager._known_programs_list_for_mock:
            # This is a generic return; specific tests might override this side_effect
            return {"program_name": name, "tracks": [], "loop_indefinitely": False, "loop_count": 0}.copy()
        raise FileNotFoundError(f"Mock FileNotFoundError for program: {name}")

    def save_program_mock_impl(name, data):
        # logger.debug(f"MOCK save_program called for: {name}")
        if name not in manager._known_programs_list_for_mock:
            manager._known_programs_list_for_mock.append(name)
        # Could store 'data' in manager._saved_data[name] = data.copy() if needed to verify saved content
        return True

    def delete_program_mock_impl(name):
        # logger.debug(f"MOCK delete_program called for: {name}")
        if name in manager._known_programs_list_for_mock:
            manager._known_programs_list_for_mock.remove(name)
        return True

    manager.list_programs.side_effect = list_programs_mock_impl
    manager.load_program.side_effect = load_program_mock_impl
    manager.save_program.side_effect = save_program_mock_impl
    manager.delete_program.side_effect = delete_program_mock_impl

    # For tests to access the initial state if they modify _known_programs_list_for_mock
    manager._initial_known_programs_list_for_mock = list(manager._known_programs_list_for_mock)
    return manager


@pytest.fixture
def mock_track_manager():
    manager = MagicMock(spec=AudioTrackManager)
    manager.list_audio_tracks.return_value = ["track_meta1", "track_meta2"]

    def load_track_metadata_side_effect(name):
        if name in ["track_meta1", "track_meta2"]:
            return {"track_name": name, "file_path": f"{name}.mp3", "detected_duration_ms": 180000}.copy()
        raise FileNotFoundError(f"Mock FileNotFoundError for track: {name}")

    manager.load_track_metadata.side_effect = load_track_metadata_side_effect
    return manager


@pytest.fixture
def audio_program_editor(qapp, mock_program_manager, mock_track_manager, tmp_path, mocker):
    dummy_icon_file = tmp_path / "dummy_icon.png"
    if not dummy_icon_file.exists(): dummy_icon_file.touch()
    media_dir = tmp_path / "media";
    os.makedirs(media_dir, exist_ok=True)

    # Reset the known programs list for the mock_program_manager at the start of each test using this fixture
    # This ensures test isolation for list_programs and load_program behavior.
    mock_program_manager._known_programs_list_for_mock = list(
        mock_program_manager._initial_known_programs_list_for_mock)
    # Reset call counts too for pristine state for each test using this fixture
    mock_program_manager.list_programs.reset_mock()
    mock_program_manager.load_program.reset_mock()
    mock_program_manager.save_program.reset_mock()

    mocker.patch('myapp.gui.audio_program_editor_window.AudioProgramManager', return_value=mock_program_manager)
    mocker.patch('myapp.gui.audio_program_editor_window.AudioTrackManager', return_value=mock_track_manager)
    mocker.patch('myapp.gui.audio_program_editor_window.get_icon_file_path', return_value=str(dummy_icon_file))
    mocker.patch('myapp.gui.widget_helpers.get_icon_file_path', return_value=str(dummy_icon_file))
    mocker.patch('myapp.gui.audio_track_player_panel.get_media_file_path', side_effect=lambda x: str(media_dir / x))

    mocker.patch.object(QMediaPlayer, 'setAudioOutput');
    mocker.patch.object(QMediaPlayer, 'play')
    mocker.patch.object(QMediaPlayer, 'pause');
    mocker.patch.object(QMediaPlayer, 'stop')
    mocker.patch.object(QMediaPlayer, 'setSource');
    mocker.patch.object(QMediaPlayer, 'position', return_value=0)
    mocker.patch.object(QMediaPlayer, 'duration', return_value=0);
    mocker.patch.object(QMediaPlayer, 'mediaStatus', return_value=QMediaPlayer.MediaStatus.NoMedia)
    mocker.patch.object(QMediaPlayer, 'playbackState', return_value=QMediaPlayer.PlaybackState.StoppedState)
    mocker.patch.object(QMediaPlayer, 'errorString', return_value="");
    mocker.patch.object(QMediaPlayer, 'error', return_value=QMediaPlayer.Error.NoError)
    mocker.patch.object(QAudioOutput, 'setVolume')

    editor = AudioProgramEditorWindow(parent=None)
    return editor


def test_editor_creation_and_program_listing(audio_program_editor, mock_program_manager):
    assert audio_program_editor is not None
    assert "Audio Program Editor" in audio_program_editor.windowTitle()
    # list_programs is called once by AudioProgramEditorWindow._refresh_all_program_data_and_ui
    mock_program_manager.list_programs.assert_called_once()
    assert audio_program_editor.program_list_panel.program_list_widget.count() == 2
    assert audio_program_editor.current_program_name == "program1"


@patch('PySide6.QtWidgets.QInputDialog.getText', return_value=("new_program", True))
def test_add_program(mock_input_dialog, audio_program_editor, mock_program_manager):
    # mock_program_manager.list_programs was called once during fixture setup.
    calls_before_add = mock_program_manager.list_programs.call_count
    assert calls_before_add == 1

    # Action: This will call list_programs twice internally:
    # 1. For existence check (sees original list from mock)
    # 2. For refresh after save (sees updated list due to save_program.side_effect)
    audio_program_editor.program_list_panel.add_program()

    mock_program_manager.save_program.assert_called_with(
        "new_program",
        {"program_name": "new_program", "tracks": [], "loop_indefinitely": False, "loop_count": 0}
    )
    # ***** MODIFICATION START *****
    assert mock_program_manager.list_programs.call_count == calls_before_add + 2
    # ***** MODIFICATION END *****

    program_names_in_ui = [audio_program_editor.program_list_panel.program_list_widget.item(i).text()
                           for i in range(audio_program_editor.program_list_panel.program_list_widget.count())]
    assert "new_program" in program_names_in_ui, f"UI list: {program_names_in_ui}"
    assert audio_program_editor.program_list_panel.get_selected_program_name() == "new_program"
    assert audio_program_editor.current_program_name == "new_program"


@patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=("track_meta1", True))
def test_add_track_to_program(mock_input_dialog, audio_program_editor, mock_program_manager):
    # Select "program1" which is loaded with empty tracks by the mock_program_manager fixture
    audio_program_editor.program_list_panel.select_program("program1")
    assert audio_program_editor.current_program_name == "program1"
    assert audio_program_editor.programs_cache["program1"]["tracks"] == []

    with patch.object(audio_program_editor.track_in_program_manager, 'add_track_to_program') as mock_add_track_method:
        audio_program_editor.add_track_to_program_dialog()
        mock_add_track_method.assert_called_once_with("track_meta1")


def test_select_track_updates_player_ui(audio_program_editor, mock_program_manager, mock_track_manager, tmp_path,
                                        mocker):
    program_name_for_test = "program_with_track"
    track_meta_name = "track_meta1"
    dummy_media_file_name = f"{track_meta_name}.mp3"

    media_dir_from_fixture = tmp_path / "media"
    dummy_media_full_path = media_dir_from_fixture / dummy_media_file_name
    if not dummy_media_full_path.exists(): dummy_media_full_path.touch()

    program_data_for_test = {
        "program_name": program_name_for_test,
        "tracks": [{"track_name": track_meta_name, "play_order": 0, "user_start_time_ms": 0, "user_end_time_ms": None}],
        "loop_indefinitely": False, "loop_count": 0
    }

    # Ensure the mock_program_manager knows about "program_with_track" for list_programs
    # and can load its specific data.
    mock_program_manager._known_programs_list_for_mock.append(program_name_for_test)

    original_load_side_effect = mock_program_manager.load_program.side_effect  # Capture the general one

    def temp_load_program_side_effect(name):
        if name == program_name_for_test:
            return program_data_for_test.copy()
        return original_load_side_effect(name)  # Fallback to general mock for other names

    mock_program_manager.load_program.side_effect = temp_load_program_side_effect

    # Action: This should refresh the panel's list and select "program_with_track"
    # This will trigger _handle_program_selected_from_list_panel in the editor
    audio_program_editor.program_list_panel.load_and_list_programs(select_program_name=program_name_for_test)

    # Assertions for main editor state
    assert audio_program_editor.current_program_name == program_name_for_test, \
        f"Editor current_program_name: Expected '{program_name_for_test}', Got '{audio_program_editor.current_program_name}'"

    cached_data = audio_program_editor.programs_cache.get(program_name_for_test)
    assert cached_data is not None, f"Program '{program_name_for_test}' not found in editor cache."
    assert cached_data["tracks"] == program_data_for_test["tracks"], "Tracks in editor cache mismatch."

    assert audio_program_editor.track_in_program_manager.current_program_name == program_name_for_test
    assert audio_program_editor.track_in_program_manager.current_program_data is not None
    assert audio_program_editor.track_in_program_manager.current_program_data["tracks"] == program_data_for_test[
        "tracks"]

    assert len(audio_program_editor.track_in_program_manager._get_program_tracks_list()) == 1

    mock_set_source_on_player_panel_instance = mocker.patch.object(audio_program_editor.track_player_panel.media_player,
                                                                   'setSource')

    assert audio_program_editor.tracks_table_widget.rowCount() > 0, "Tracks table not populated."
    audio_program_editor.tracks_table_widget.selectRow(0)

    expected_qurl = QUrl.fromLocalFile(str(dummy_media_full_path))
    mock_set_source_on_player_panel_instance.assert_called_once_with(expected_qurl)

    player_label_text = audio_program_editor.track_player_panel.loaded_track_label.text()
    assert player_label_text.startswith("Loading:") or player_label_text.startswith("Ready:")

    # Clean up changes to the shared mock for subsequent tests if not handled by fixture scope
    if program_name_for_test in mock_program_manager._known_programs_list_for_mock:
        mock_program_manager._known_programs_list_for_mock.remove(program_name_for_test)
    mock_program_manager.load_program.side_effect = original_load_side_effect