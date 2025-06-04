# tests/test_audio/test_audio_track_manager.py
import pytest
import os
import json
import shutil
from unittest.mock import patch, \
    MagicMock  # Ensure MagicMock is imported if used, though not in this specific file's direct code
import sys

# Add project root to sys.path if tests are run from a different CWD
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from myapp.audio.audio_track_manager import AudioTrackManager
from myapp.utils.schemas import AUDIO_TRACK_METADATA_SCHEMA  # For type hints if needed
from myapp.utils.json_validator import validate_json  # For direct validation if needed by tests


# Fixture to create a temporary directory for audio tracks metadata
@pytest.fixture
def temp_audio_tracks_dir(tmp_path):
    # tmp_path is a built-in pytest fixture providing a temporary directory path object
    d = tmp_path / "audio_tracks_meta"
    d.mkdir()
    return str(d)  # Return as string, as os.path functions expect strings


# Fixture for AudioTrackManager instance using the temp directory
@pytest.fixture
def audio_track_manager(temp_audio_tracks_dir):
    """Provides an AudioTrackManager instance configured to use the temp directory."""
    # Patch get_audio_tracks_path to return the temp_audio_tracks_dir for this test session
    with patch('myapp.audio.audio_track_manager.get_audio_tracks_path', return_value=temp_audio_tracks_dir):
        manager = AudioTrackManager()
    return manager


def test_audio_track_manager_init(audio_track_manager, temp_audio_tracks_dir):
    """Test if AudioTrackManager initializes correctly and creates its directory."""
    assert audio_track_manager.tracks_dir == temp_audio_tracks_dir
    assert os.path.exists(temp_audio_tracks_dir)


def test_save_and_load_track_metadata(audio_track_manager):
    track_name = "test_track"
    metadata_to_save = {
        "track_name": track_name,  # Will be overwritten by save_track_metadata to match key
        "file_path": "test_file.mp3",
        "detected_duration_ms": 123456
    }
    assert audio_track_manager.save_track_metadata(track_name, metadata_to_save)

    loaded_metadata = audio_track_manager.load_track_metadata(track_name)
    assert loaded_metadata is not None
    assert loaded_metadata["track_name"] == track_name  # Ensure track_name in data is correct
    assert loaded_metadata["file_path"] == "test_file.mp3"
    assert loaded_metadata["detected_duration_ms"] == 123456


def test_load_track_metadata_not_found(audio_track_manager):
    assert audio_track_manager.load_track_metadata("non_existent_track") is None


@patch('myapp.audio.audio_track_manager.validate_json')  # Patch validate_json for this test
def test_save_invalid_track_metadata_schema(mock_validate_json, audio_track_manager):
    mock_validate_json.return_value = (False, MagicMock(message="Schema error"))  # Simulate validation failure
    track_name = "invalid_schema_track"
    metadata = {"track_name": track_name, "file_path": "file.mp3", "unexpected_field": "bad_data"}

    # The save method currently logs a warning and attempts to save anyway.
    # If strict validation is enforced (i.e., save returns False or raises error on validation fail),
    # this test would need to assert that behavior.
    # For now, we just check that validate_json was called.
    audio_track_manager.save_track_metadata(track_name, metadata)
    mock_validate_json.assert_called_once()
    # To make this test more robust, if save_track_metadata's behavior on validation failure changes,
    # this test should reflect that (e.g., assert it returns False or raises an error).


def test_save_track_metadata_missing_media_file(audio_track_manager, tmp_path):
    """
    Tests create_metadata_from_file which handles media file copying and metadata saving.
    This test focuses on the metadata creation part when the source audio file might be missing.
    """
    non_existent_audio_file = tmp_path / "non_existent.mp3"
    metadata, error = audio_track_manager.create_metadata_from_file("test_track", str(non_existent_audio_file))
    assert metadata is None
    assert error is not None
    assert "Source audio file not found" in error


def test_list_audio_tracks(audio_track_manager):
    assert audio_track_manager.list_audio_tracks() == []
    audio_track_manager.save_track_metadata("track1", {"track_name": "track1", "file_path": "f1.mp3",
                                                       "detected_duration_ms": 100})
    audio_track_manager.save_track_metadata("track2", {"track_name": "track2", "file_path": "f2.mp3",
                                                       "detected_duration_ms": 200})
    assert sorted(audio_track_manager.list_audio_tracks()) == ["track1", "track2"]


def test_delete_track_metadata(audio_track_manager):
    track_name = "track_to_delete"
    audio_track_manager.save_track_metadata(track_name,
                                            {"track_name": track_name, "file_path": "f.mp3", "detected_duration_ms": 0})
    assert os.path.exists(audio_track_manager.get_track_metadata_path(track_name))
    assert audio_track_manager.delete_track_metadata(track_name)
    assert not os.path.exists(audio_track_manager.get_track_metadata_path(track_name))
    assert not audio_track_manager.delete_track_metadata("non_existent_track")  # Deleting non-existent


# The following tests for `detect_audio_duration` assume such a method exists.
# Since AudioTrackManager was modified to set detected_duration_ms to None in create_metadata_from_file,
# these tests would need to be adapted if a standalone detect_audio_duration method is added later
# or if create_metadata_from_file starts doing real detection.
# For now, I'll comment them out as they were likely for a previous version or a planned feature
# that is not currently implemented directly as `detect_audio_duration` method.

# def test_detect_audio_duration_valid(audio_track_manager, tmp_path):
#     # This test requires a real audio file and a duration detection mechanism in AudioTrackManager
#     # For example, if using mutagen:
#     # Create a dummy mp3 file or use a known small mp3
#     # Pass its path to a method that uses mutagen (e.g., audio_track_manager.detect_audio_duration)
#     # For now, this test will be conceptual as detect_audio_duration isn't fully implemented
#     pass

# def test_detect_audio_duration_mutagen_error(audio_track_manager, tmp_path):
#     # Test scenario where mutagen (or other library) fails to read the file
#     pass

# def test_detect_audio_duration_file_not_found(audio_track_manager):
#     # Test scenario where the audio file path is invalid
#     pass

def test_load_metadata_with_duration_redetection(audio_track_manager):
    """
    This test is more relevant if load_track_metadata had an option to re-detect duration.
    Currently, it just loads what's in the JSON.
    """
    track_name = "test_track_redetect"
    initial_metadata = {
        "track_name": track_name,
        "file_path": "test_file.mp3",
        "detected_duration_ms": 1000  # Initial dummy duration
    }
    audio_track_manager.save_track_metadata(track_name, initial_metadata)

    loaded_metadata = audio_track_manager.load_track_metadata(track_name)
    assert loaded_metadata is not None
    assert loaded_metadata["detected_duration_ms"] == 1000
    # If redetection logic existed and was triggered, this assertion would change.


def test_create_metadata_from_file_success(audio_track_manager, tmp_path):
    """Test successful creation of metadata and copying of media file."""
    source_audio_dir = tmp_path / "source_audio"
    source_audio_dir.mkdir()
    source_audio_file = source_audio_dir / "sample.mp3"
    with open(source_audio_file, "w") as f: f.write("dummy audio content")  # Create dummy file

    media_dir_patch = tmp_path / "media"  # Assume get_media_file_path uses this
    media_dir_patch.mkdir(exist_ok=True)

    track_name = "new_sample_track"

    with patch('myapp.audio.audio_track_manager.get_media_file_path', lambda x: str(media_dir_patch / x)):
        metadata, error = audio_track_manager.create_metadata_from_file(track_name, str(source_audio_file))

    assert error is None
    assert metadata is not None
    assert metadata["track_name"] == track_name
    assert metadata["file_path"] == "sample.mp3"
    assert metadata["detected_duration_ms"] is None  # As per current implementation

    # Check if metadata file was saved
    expected_metadata_path = audio_track_manager.get_track_metadata_path(track_name)
    assert os.path.exists(expected_metadata_path)

    # Check if media file was copied
    expected_media_path = media_dir_patch / "sample.mp3"
    assert os.path.exists(expected_media_path)