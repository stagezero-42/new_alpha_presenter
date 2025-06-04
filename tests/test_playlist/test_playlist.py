# tests/test_playlist/test_playlist.py
import pytest
import os
import json
import shutil
from unittest.mock import patch, MagicMock
from myapp.playlist.playlist import Playlist, get_default_slide_audio_settings  # Import getter
from myapp.utils.schemas import DEFAULT_AUDIO_PROGRAM_VOLUME  # Import default


@pytest.fixture
def temp_playlist_dir(tmp_path):
    playlist_dir = tmp_path / "playlists"
    playlist_dir.mkdir()
    yield str(playlist_dir)


@pytest.fixture
def valid_playlist_file(temp_playlist_dir):
    # This content does NOT initially include the new audio fields
    # The Playlist.load() method should add them with defaults.
    playlist_content = {
        "slides": [
            {"layers": ["image1.png"], "duration": 5, "loop_to_slide": 0, "text_overlay": None,
             "audio_program_name": None},
            {"layers": ["image2.png"], "duration": 0, "loop_to_slide": 2, "text_overlay": None,
             "audio_program_name": None}
        ]
    }
    playlist_path = os.path.join(temp_playlist_dir, "test_playlist.json")
    with open(playlist_path, "w") as f:
        json.dump(playlist_content, f)
    return playlist_path


@pytest.fixture
def invalid_schema_playlist_file(temp_playlist_dir):
    playlist_content = {"slides": [
        {"layers": ["image1.png"], "duration": "five", "audio_program_name": None}]}  # duration is wrong type
    playlist_path = os.path.join(temp_playlist_dir, "invalid_schema.json")
    with open(playlist_path, "w") as f:
        json.dump(playlist_content, f)
    return playlist_path


@pytest.fixture
def playlist_instance(temp_playlist_dir):
    with patch('myapp.playlist.playlist.get_playlists_path', return_value=temp_playlist_dir):
        playlist = Playlist()
        # Ensure slides attribute exists, even if empty, matching typical initialization
        if not hasattr(playlist, 'slides') or playlist.slides is None:
            playlist.slides = []
        yield playlist


@patch('myapp.playlist.playlist.validate_json', return_value=(True, None))
def test_playlist_load_valid(mock_validate, valid_playlist_file):
    with patch('myapp.playlist.playlist.get_playlists_path', return_value=os.path.dirname(valid_playlist_file)):
        playlist = Playlist(valid_playlist_file)
        mock_validate.assert_called_once()
        assert len(playlist.get_slides()) == 2

        # Expected data now includes new audio fields with defaults
        expected_slide_0 = {
            "layers": ["image1.png"], "duration": 5, "loop_to_slide": 0,
            "text_overlay": None, "audio_program_name": None,
            "loop_audio_program": False,  # Default
            "audio_intro_delay_ms": 0,  # Default
            "audio_outro_duration_ms": 0,  # Default
            "audio_program_volume": DEFAULT_AUDIO_PROGRAM_VOLUME  # Default
        }
        assert playlist.get_slide(0) == expected_slide_0
        assert playlist.file_path == valid_playlist_file
        assert playlist.get_playlists_directory() == os.path.dirname(valid_playlist_file)


def test_playlist_load_invalid_schema(invalid_schema_playlist_file):
    with patch('myapp.playlist.playlist.get_playlists_path',
               return_value=os.path.dirname(invalid_schema_playlist_file)):
        with pytest.raises(ValueError, match="Playlist file has invalid format"):
            Playlist(invalid_schema_playlist_file)


def test_playlist_load_not_found(playlist_instance):
    with pytest.raises(FileNotFoundError):
        playlist_instance.load(os.path.join(playlist_instance.get_playlists_directory(), "non_existent_playlist.json"))


@patch('myapp.playlist.playlist.validate_json', return_value=(True, None))
def test_playlist_save_and_load(mock_validate, playlist_instance, temp_playlist_dir):
    slide_content_to_add = {"layers": ["new_image.png"], "duration": 10, "loop_to_slide": 1}
    playlist_instance.add_slide(slide_content_to_add)  # add_slide applies defaults

    save_path = os.path.join(temp_playlist_dir, "new_playlist.json")
    playlist_instance.save(save_path)

    loaded_playlist = Playlist(save_path)
    assert len(loaded_playlist.get_slides()) == 1

    # Build expected dictionary including all defaults that add_slide and load would apply
    expected_loaded_slide = {
        "layers": ["new_image.png"], "duration": 10, "loop_to_slide": 1,
        "text_overlay": None,  # Default from add_slide
        **get_default_slide_audio_settings()  # Get all audio defaults
    }
    # Since audio_program_name is None, loop_audio_program, intro/outro, volume might be omitted on save
    # if they match defaults AND audio_program_name is None.
    # Playlist.load will re-apply them. So compare against what load produces.

    actual_loaded_slide = loaded_playlist.get_slide(0)

    # Check core fields first
    assert actual_loaded_slide["layers"] == expected_loaded_slide["layers"]
    assert actual_loaded_slide["duration"] == expected_loaded_slide["duration"]
    assert actual_loaded_slide["loop_to_slide"] == expected_loaded_slide["loop_to_slide"]
    assert actual_loaded_slide["text_overlay"] == expected_loaded_slide["text_overlay"]

    # Check that all default audio settings are present after load
    default_audio = get_default_slide_audio_settings()
    assert actual_loaded_slide["audio_program_name"] == default_audio["audio_program_name"]  # Should be None
    assert actual_loaded_slide["loop_audio_program"] == default_audio["loop_audio_program"]
    assert actual_loaded_slide["audio_intro_delay_ms"] == default_audio["audio_intro_delay_ms"]
    assert actual_loaded_slide["audio_outro_duration_ms"] == default_audio["audio_outro_duration_ms"]
    assert actual_loaded_slide["audio_program_volume"] == default_audio["audio_program_volume"]

    assert mock_validate.call_count >= 1  # Called by Playlist init and save


def test_playlist_add_remove_slide(playlist_instance):
    playlist_instance.add_slide({"layers": ["image1.png"], "duration": 0, "loop_to_slide": 0})
    assert len(playlist_instance.get_slides()) == 1
    slide_content = playlist_instance.get_slide(0)
    assert slide_content.get("text_overlay") is None
    # Check new default audio fields
    default_audio = get_default_slide_audio_settings()
    assert slide_content.get("audio_program_name") == default_audio["audio_program_name"]
    assert slide_content.get("loop_audio_program") == default_audio["loop_audio_program"]
    assert slide_content.get("audio_intro_delay_ms") == default_audio["audio_intro_delay_ms"]
    assert slide_content.get("audio_outro_duration_ms") == default_audio["audio_outro_duration_ms"]
    assert slide_content.get("audio_program_volume") == default_audio["audio_program_volume"]

    playlist_instance.remove_slide(0)
    assert len(playlist_instance.get_slides()) == 0