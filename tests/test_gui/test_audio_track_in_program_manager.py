# tests/test_gui/test_audio_track_in_program_manager.py
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QTableWidget, QSpinBox
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.audio_track_in_program_manager import AudioTrackInProgramManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_editor_window():
    window = MagicMock()
    window.update_ui_state = MagicMock()
    window.update_audio_player_ui_for_track = MagicMock()
    return window


@pytest.fixture
def tracks_table(qapp):
    table = QTableWidget()
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(["Track Name", "Start (ms)", "End (ms)"])
    return table


@pytest.fixture
def track_in_program_manager(mock_editor_window, tracks_table):
    manager = AudioTrackInProgramManager(mock_editor_window, tracks_table)
    return manager


@pytest.fixture
def sample_program_with_tracks():
    # Return a deep copy each time to avoid modification across tests
    return {
        "program_name": "test_prog",
        "tracks": [
            {"track_name": "track1", "play_order": 0, "user_start_time_ms": 1000, "user_end_time_ms": 10000},
            {"track_name": "track2", "play_order": 1, "user_start_time_ms": 0, "user_end_time_ms": None},
        ],
        "loop_indefinitely": False,
        "loop_count": 0
    }


def test_manager_creation(track_in_program_manager, tracks_table):
    assert track_in_program_manager.tracks_table_widget is tracks_table
    assert track_in_program_manager.editor_window is not None


def test_set_current_program_populates_table(track_in_program_manager, sample_program_with_tracks, tracks_table):
    program_data = sample_program_with_tracks.copy()  # Use a copy
    track_in_program_manager.set_current_program("test_prog", program_data)

    assert tracks_table.rowCount() == 2
    assert tracks_table.item(0, AudioTrackInProgramManager.COL_TRACK_NAME).text() == "track1"
    start_spin_0 = tracks_table.cellWidget(0, AudioTrackInProgramManager.COL_START_TIME)
    assert isinstance(start_spin_0, QSpinBox)
    assert start_spin_0.value() == 1000

    end_spin_1 = tracks_table.cellWidget(1, AudioTrackInProgramManager.COL_END_TIME)
    assert isinstance(end_spin_1, QSpinBox)
    assert end_spin_1.value() == 0


def test_add_track_to_program(track_in_program_manager, tracks_table):
    empty_program = {"program_name": "empty_prog", "tracks": [], "loop_indefinitely": False, "loop_count": 0}
    track_in_program_manager.set_current_program("empty_prog", empty_program)

    assert tracks_table.rowCount() == 0

    mock_slot = MagicMock()
    track_in_program_manager.program_tracks_updated.connect(mock_slot)

    track_in_program_manager.add_track_to_program("new_metadata_track")

    assert tracks_table.rowCount() == 1
    assert tracks_table.item(0, AudioTrackInProgramManager.COL_TRACK_NAME).text() == "new_metadata_track"
    assert empty_program["tracks"][0]["track_name"] == "new_metadata_track"
    assert empty_program["tracks"][0]["play_order"] == 0
    mock_slot.assert_called_once()

    track_in_program_manager.program_tracks_updated.disconnect(mock_slot)


def test_remove_selected_track(track_in_program_manager, sample_program_with_tracks, tracks_table):
    program_data = sample_program_with_tracks.copy()  # Use a copy
    track_in_program_manager.set_current_program("test_prog", program_data)
    tracks_table.selectRow(0)

    assert tracks_table.rowCount() == 2

    mock_slot = MagicMock()
    track_in_program_manager.program_tracks_updated.connect(mock_slot)

    track_in_program_manager.remove_selected_track_from_program()

    assert tracks_table.rowCount() == 1
    assert tracks_table.item(0, AudioTrackInProgramManager.COL_TRACK_NAME).text() == "track2"
    assert len(program_data["tracks"]) == 1
    assert program_data["tracks"][0]["track_name"] == "track2"
    assert program_data["tracks"][0]["play_order"] == 0
    mock_slot.assert_called_once()

    track_in_program_manager.program_tracks_updated.disconnect(mock_slot)


def test_handle_time_spinbox_changed(track_in_program_manager, sample_program_with_tracks, tracks_table):
    program_data = sample_program_with_tracks.copy()  # Use a copy
    track_in_program_manager.set_current_program("test_prog", program_data)

    start_spin = tracks_table.cellWidget(0, AudioTrackInProgramManager.COL_START_TIME)
    assert isinstance(start_spin, QSpinBox)

    mock_slot = MagicMock()
    track_in_program_manager.program_tracks_updated.connect(mock_slot)

    start_spin.setValue(2500)

    assert program_data["tracks"][0]["user_start_time_ms"] == 2500
    mock_slot.assert_called_once()

    track_in_program_manager.program_tracks_updated.disconnect(mock_slot)