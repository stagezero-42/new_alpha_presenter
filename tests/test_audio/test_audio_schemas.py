# tests/test_audio/test_audio_schemas.py
import pytest
from jsonschema.exceptions import ValidationError
import os  # <--- ADD THIS LINE
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.utils.json_validator import validate_json
from myapp.utils.schemas import (
    AUDIO_TRACK_METADATA_SCHEMA,
    AUDIO_PROGRAM_TRACK_ENTRY_SCHEMA,
    AUDIO_PROGRAM_SCHEMA
)


# --- Tests for AUDIO_TRACK_METADATA_SCHEMA ---
def test_valid_audio_track_metadata():
    data = {"track_name": "my_song", "file_path": "audio/my_song.mp3", "detected_duration_ms": 180000}
    is_valid, error = validate_json(data, AUDIO_TRACK_METADATA_SCHEMA)
    assert is_valid is True
    assert error is None


def test_invalid_audio_track_metadata_missing_required():
    data = {"file_path": "audio/my_song.mp3"}  # Missing track_name
    is_valid, error = validate_json(data, AUDIO_TRACK_METADATA_SCHEMA)
    assert is_valid is False
    assert isinstance(error, ValidationError)
    assert "'track_name' is a required property" in error.message


def test_invalid_audio_track_metadata_wrong_type():
    data = {"track_name": "my_song", "file_path": 123, "detected_duration_ms": "long"}  # wrong types
    is_valid, error = validate_json(data, AUDIO_TRACK_METADATA_SCHEMA)
    assert is_valid is False
    assert isinstance(error, ValidationError)
    # Add more specific checks for which field failed if necessary


# --- Tests for AUDIO_PROGRAM_TRACK_ENTRY_SCHEMA ---
def test_valid_audio_program_track_entry():
    data = {"track_name": "theme_music", "play_order": 0, "user_start_time_ms": 0, "user_end_time_ms": 30000}
    is_valid, error = validate_json(data, AUDIO_PROGRAM_TRACK_ENTRY_SCHEMA)
    assert is_valid is True
    assert error is None


def test_valid_audio_program_track_entry_null_end_time():
    data = {"track_name": "theme_music", "play_order": 0, "user_start_time_ms": 0, "user_end_time_ms": None}
    is_valid, error = validate_json(data, AUDIO_PROGRAM_TRACK_ENTRY_SCHEMA)
    assert is_valid is True
    assert error is None


def test_invalid_audio_program_track_entry_negative_start():
    data = {"track_name": "theme_music", "play_order": 0, "user_start_time_ms": -100}
    is_valid, error = validate_json(data, AUDIO_PROGRAM_TRACK_ENTRY_SCHEMA)
    assert is_valid is False
    assert isinstance(error, ValidationError)


# --- Tests for AUDIO_PROGRAM_SCHEMA ---
def test_valid_audio_program():
    data = {
        "program_name": "morning_mix",
        "tracks": [
            {"track_name": "song1", "play_order": 0, "user_start_time_ms": 0},
            {"track_name": "song2", "play_order": 1, "user_start_time_ms": 1000, "user_end_time_ms": 60000}
        ],
        "loop_indefinitely": True,
        "loop_count": 0
    }
    is_valid, error = validate_json(data, AUDIO_PROGRAM_SCHEMA)
    assert is_valid is True
    assert error is None


def test_invalid_audio_program_bad_track_entry():
    data = {
        "program_name": "morning_mix",
        "tracks": [{"play_order": "first"}]  # track_name missing, play_order wrong type
    }
    is_valid, error = validate_json(data, AUDIO_PROGRAM_SCHEMA)
    assert is_valid is False
    assert isinstance(error, ValidationError)


def test_invalid_audio_program_bad_loop_type():
    data = {"program_name": "test", "tracks": [], "loop_indefinitely": "maybe"}
    is_valid, error = validate_json(data, AUDIO_PROGRAM_SCHEMA)
    assert is_valid is False
    assert isinstance(error, ValidationError)