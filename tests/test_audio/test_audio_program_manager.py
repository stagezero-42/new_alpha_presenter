# tests/test_audio/test_audio_program_manager.py
import pytest
import os
import json
from unittest.mock import patch

# Ensure the myapp structure can be imported
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.audio.audio_program_manager import AudioProgramManager
from myapp.utils.schemas import AUDIO_PROGRAM_SCHEMA


@pytest.fixture
def temp_audio_programs_dir(tmp_path):
    """Creates a temporary directory for audio programs."""
    audio_programs_dir = tmp_path / "audio_programs"
    audio_programs_dir.mkdir()
    yield str(audio_programs_dir)


@pytest.fixture
def audio_program_manager(temp_audio_programs_dir):
    """Provides an AudioProgramManager instance."""
    manager = AudioProgramManager(audio_programs_dir=temp_audio_programs_dir)
    return manager


@pytest.fixture
def sample_audio_program_data():
    return {
        "program_name": "chill_vibes_program",
        "tracks": [
            {
                "track_name": "lofi_beat_1",
                "play_order": 0,
                "user_start_time_ms": 0,
                "user_end_time_ms": None
            },
            {
                "track_name": "ambient_soundscape",
                "play_order": 1,
                "user_start_time_ms": 5000,  # Start 5s in
                "user_end_time_ms": 60000  # End at 1 minute
            }
        ],
        "loop_indefinitely": False,
        "loop_count": 2
    }


def test_audio_program_manager_init(audio_program_manager, temp_audio_programs_dir):
    assert audio_program_manager.audio_programs_dir == temp_audio_programs_dir
    assert os.path.exists(temp_audio_programs_dir)


def test_save_and_load_program(audio_program_manager, sample_audio_program_data):
    program_name = sample_audio_program_data["program_name"]
    result = audio_program_manager.save_program(program_name, sample_audio_program_data)
    assert result is True
    assert os.path.exists(os.path.join(audio_program_manager.audio_programs_dir, f"{program_name}.json"))

    loaded_data = audio_program_manager.load_program(program_name)
    assert loaded_data == sample_audio_program_data


def test_load_program_not_found(audio_program_manager):
    with pytest.raises(FileNotFoundError):
        audio_program_manager.load_program("non_existent_program")


def test_save_invalid_program_schema(audio_program_manager, sample_audio_program_data):
    invalid_data = sample_audio_program_data.copy()
    invalid_data["loop_count"] = "many"  # Invalid type
    result = audio_program_manager.save_program(invalid_data["program_name"], invalid_data)
    assert result is False


def test_list_programs(audio_program_manager, sample_audio_program_data):
    assert audio_program_manager.list_programs() == []

    name1 = sample_audio_program_data["program_name"]
    audio_program_manager.save_program(name1, sample_audio_program_data)

    name2 = "another_program"
    audio_program_manager.save_program(name2, {"program_name": name2, "tracks": [], "loop_indefinitely": True,
                                               "loop_count": 0})

    listed = sorted(audio_program_manager.list_programs())
    assert listed == sorted([name1, name2])


def test_delete_program(audio_program_manager, sample_audio_program_data):
    program_name = sample_audio_program_data["program_name"]
    file_path = os.path.join(audio_program_manager.audio_programs_dir, f"{program_name}.json")

    audio_program_manager.save_program(program_name, sample_audio_program_data)
    assert os.path.exists(file_path)

    result = audio_program_manager.delete_program(program_name)
    assert result is True
    assert not os.path.exists(file_path)

    result_non_existent = audio_program_manager.delete_program("non_existent_program")
    assert result_non_existent is True


def test_load_program_name_mismatch(audio_program_manager, temp_audio_programs_dir):
    """Tests loading a file where internal name differs from filename."""
    file_program_name = "file_name_program"
    internal_program_name = "internal_name_program"
    data = {
        "program_name": internal_program_name,
        "tracks": [],
        "loop_indefinitely": False,
        "loop_count": 0
    }
    file_path = os.path.join(temp_audio_programs_dir, f"{file_program_name}.json")
    with open(file_path, "w") as f:
        json.dump(data, f)

    loaded_data = audio_program_manager.load_program(file_program_name)
    assert loaded_data["program_name"] == file_program_name  # Should be corrected

# Add more tests for filename safety, other schema violations, etc.