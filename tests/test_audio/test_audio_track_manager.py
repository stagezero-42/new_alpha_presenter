# tests/test_audio/test_audio_track_manager.py
import pytest
import os
import json
from unittest.mock import patch, MagicMock

# Ensure the myapp structure can be imported
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.audio.audio_track_manager import AudioTrackManager
from myapp.utils.schemas import AUDIO_TRACK_METADATA_SCHEMA
from myapp.utils.paths import get_media_file_path  # For creating dummy media files


@pytest.fixture
def temp_audio_tracks_dir(tmp_path):
    """Creates a temporary directory for audio track metadata."""
    audio_tracks_dir = tmp_path / "audio_tracks_meta"
    audio_tracks_dir.mkdir()
    # Also create a dummy media directory for duration detection tests
    dummy_media_dir = tmp_path / "media"
    dummy_media_dir.mkdir()
    with patch('myapp.utils.paths.get_media_path', return_value=str(dummy_media_dir)):
        yield str(audio_tracks_dir)


@pytest.fixture
def audio_track_manager(temp_audio_tracks_dir):
    """Provides an AudioTrackManager instance configured with the temp directory."""
    manager = AudioTrackManager(audio_tracks_dir=temp_audio_tracks_dir)
    return manager


@pytest.fixture
def sample_track_metadata():
    return {
        "track_name": "sample_track_1",
        "file_path": "sample_audio.mp3",
        "detected_duration_ms": 120000  # 2 minutes
    }


# Helper to create a dummy audio file for duration detection tests
def create_dummy_audio_file(media_dir, filename, duration_s=10.0):
    file_path = os.path.join(media_dir, filename)
    # This is a very simplified mock. Real duration detection needs a real file
    # or a more sophisticated mock of mutagen.File
    with open(file_path, "w") as f:
        f.write("dummy audio content")  # Not a real audio file

    # Mock mutagen.File to return a mock object with an info attribute
    mock_audio_info = MagicMock()
    mock_audio_info.length = duration_s

    mock_mutagen_file = MagicMock()
    mock_mutagen_file.info = mock_audio_info

    # This patch needs to be active when detect_audio_duration is called
    # It might be better to apply this patch within the specific test
    # return file_path, patch('mutagen.File', return_value=mock_mutagen_file)
    return file_path


def test_audio_track_manager_init(audio_track_manager, temp_audio_tracks_dir):
    """Tests if the manager initializes and creates the directory."""
    assert audio_track_manager.audio_tracks_dir == temp_audio_tracks_dir
    assert os.path.exists(temp_audio_tracks_dir)


def test_save_and_load_track_metadata(audio_track_manager, sample_track_metadata, tmp_path):
    """Tests saving valid track metadata and loading it back."""
    track_name = sample_track_metadata["track_name"]
    media_file_path = tmp_path / "media" / sample_track_metadata["file_path"]
    media_file_path.parent.mkdir(exist_ok=True)
    media_file_path.touch()  # Ensure media file exists for path check in save

    result = audio_track_manager.save_track_metadata(track_name, sample_track_metadata)
    assert result is True
    assert os.path.exists(os.path.join(audio_track_manager.audio_tracks_dir, f"{track_name}.json"))

    loaded_data = audio_track_manager.load_track_metadata(track_name)
    assert loaded_data == sample_track_metadata


def test_load_track_metadata_not_found(audio_track_manager):
    """Tests loading metadata that doesn't exist."""
    with pytest.raises(FileNotFoundError):
        audio_track_manager.load_track_metadata("non_existent_track")


def test_save_invalid_track_metadata_schema(audio_track_manager, sample_track_metadata):
    """Tests saving metadata that violates the schema."""
    invalid_data = sample_track_metadata.copy()
    invalid_data["file_path"] = 123  # Invalid type
    result = audio_track_manager.save_track_metadata(invalid_data["track_name"], invalid_data)
    assert result is False


def test_save_track_metadata_missing_media_file(audio_track_manager, sample_track_metadata):
    """Tests saving metadata when the referenced media file doesn't exist (should still save with warning)."""
    track_name = "track_with_missing_media"
    metadata = {
        "track_name": track_name,
        "file_path": "non_existent_audio.mp3", # This file won't exist in the temp media dir
        "detected_duration_ms": 10000
    }
    # Patch the logger used by the audio_track_manager module
    with patch('myapp.audio.audio_track_manager.logger') as mock_module_logger:
        result = audio_track_manager.save_track_metadata(track_name, metadata)
        assert result is True # Metadata save should still succeed
        mock_module_logger.warning.assert_called_once()
        # Optionally, check the warning message content:
        # mock_module_logger.warning.assert_called_with(
        #     "Media file 'non_existent_audio.mp3' referenced in metadata for 'track_with_missing_media' does not exist in media assets. Saving metadata anyway."
        # )


def test_list_audio_tracks(audio_track_manager, sample_track_metadata):
    """Tests listing available track metadata files."""
    assert audio_track_manager.list_audio_tracks() == []
    media_file_path = get_media_file_path(sample_track_metadata["file_path"])  # uses patched get_media_path
    os.makedirs(os.path.dirname(media_file_path), exist_ok=True)
    open(media_file_path, 'a').close()  # Touch the file

    audio_track_manager.save_track_metadata(sample_track_metadata["track_name"], sample_track_metadata)
    audio_track_manager.save_track_metadata("another_track", {"track_name": "another_track", "file_path": "another.mp3",
                                                              "detected_duration_ms": 5000})

    listed = sorted(audio_track_manager.list_audio_tracks())
    assert listed == sorted([sample_track_metadata["track_name"], "another_track"])


def test_delete_track_metadata(audio_track_manager, sample_track_metadata):
    """Tests deleting track metadata."""
    track_name = sample_track_metadata["track_name"]
    file_path = os.path.join(audio_track_manager.audio_tracks_dir, f"{track_name}.json")
    media_file_path = get_media_file_path(sample_track_metadata["file_path"])
    os.makedirs(os.path.dirname(media_file_path), exist_ok=True)
    open(media_file_path, 'a').close()

    audio_track_manager.save_track_metadata(track_name, sample_track_metadata)
    assert os.path.exists(file_path)

    result = audio_track_manager.delete_track_metadata(track_name)
    assert result is True
    assert not os.path.exists(file_path)

    # Test deleting non-existent
    result_non_existent = audio_track_manager.delete_track_metadata("non_existent_meta")
    assert result_non_existent is True  # Should not error


@patch('myapp.audio.audio_track_manager.MutagenFile')
def test_detect_audio_duration_valid(mock_mutagen_file, audio_track_manager, tmp_path):
    """Tests duration detection for a 'valid' (mocked) audio file."""
    media_dir = tmp_path / "media"  # This uses the unpatched get_media_path for setup
    # media_dir.mkdir(exist_ok=True) # Already created by fixture for manager

    mock_audio = MagicMock()
    mock_audio.info.length = 123.456  # seconds
    mock_mutagen_file.return_value = mock_audio

    dummy_file_path = os.path.join(str(media_dir), "test_song.mp3")
    open(dummy_file_path, 'w').write("dummy content")  # Create the dummy file

    duration_ms = audio_track_manager.detect_audio_duration(dummy_file_path)
    assert duration_ms == 123456
    mock_mutagen_file.assert_called_once_with(dummy_file_path, easy=True)


@patch('myapp.audio.audio_track_manager.MutagenFile', side_effect=Exception("Mutagen Error"))
def test_detect_audio_duration_mutagen_error(mock_mutagen_file_error, audio_track_manager, tmp_path):
    """Tests duration detection when Mutagen throws an error."""
    media_dir = tmp_path / "media"
    # media_dir.mkdir(exist_ok=True)
    dummy_file_path = os.path.join(str(media_dir), "error_song.mp3")
    open(dummy_file_path, 'w').write("dummy content")

    duration_ms = audio_track_manager.detect_audio_duration(dummy_file_path)
    assert duration_ms is None


def test_detect_audio_duration_file_not_found(audio_track_manager):
    """Tests duration detection for a non-existent file."""
    duration_ms = audio_track_manager.detect_audio_duration("/path/to/non_existent_audio_file.mp3")
    assert duration_ms is None


def test_load_metadata_with_duration_redetection(audio_track_manager, sample_track_metadata, tmp_path):
    """Tests if metadata loading re-detects duration if it's null."""
    track_name = sample_track_metadata["track_name"]
    metadata_no_duration = sample_track_metadata.copy()
    metadata_no_duration["detected_duration_ms"] = None

    # Prepare media file path (using the patched get_media_path via fixture)
    media_file_path = get_media_file_path(sample_track_metadata["file_path"])
    os.makedirs(os.path.dirname(media_file_path), exist_ok=True)
    open(media_file_path, 'w').write("dummy audio content")  # Create dummy media file

    audio_track_manager.save_track_metadata(track_name, metadata_no_duration)

    # Mock MutagenFile for re-detection
    mock_audio_info = MagicMock()
    mock_audio_info.length = 60.0  # New duration to detect
    mock_mutagen_file_instance = MagicMock()
    mock_mutagen_file_instance.info = mock_audio_info

    with patch('myapp.audio.audio_track_manager.MutagenFile', return_value=mock_mutagen_file_instance) as mock_mf:
        loaded_data = audio_track_manager.load_track_metadata(track_name)
        mock_mf.assert_called_once_with(media_file_path, easy=True)  # Check re-detection was attempted
        assert loaded_data["detected_duration_ms"] == 60000

# Add more tests for filename safety, other schema violations, etc.