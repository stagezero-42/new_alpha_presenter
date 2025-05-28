# tests/test_playlist/test_playlist.py
import pytest
import os
import json
import shutil
from unittest.mock import patch, MagicMock
from myapp.playlist.playlist import Playlist

@pytest.fixture
def temp_playlist_dir(tmp_path):
    """Creates a temporary directory for playlists."""
    playlist_dir = tmp_path / "playlists"
    playlist_dir.mkdir()
    yield str(playlist_dir)


@pytest.fixture
def valid_playlist_file(temp_playlist_dir):
    """Creates a valid playlist file and returns its path."""
    playlist_content = {
        "slides": [
            {"layers": ["image1.png"], "duration": 5, "loop_to_slide": 0},
            {"layers": ["image2.png"], "duration": 0, "loop_to_slide": 2}
        ]
    }
    playlist_path = os.path.join(temp_playlist_dir, "test_playlist.json")
    with open(playlist_path, "w") as f:
        json.dump(playlist_content, f)
    return playlist_path

@pytest.fixture
def invalid_schema_playlist_file(temp_playlist_dir):
    """Creates a playlist file that violates the schema."""
    playlist_content = {"slides": [{"layers": ["image1.png"], "duration": "five"}]} # Duration is string
    playlist_path = os.path.join(temp_playlist_dir, "invalid_schema.json")
    with open(playlist_path, "w") as f:
        json.dump(playlist_content, f)
    return playlist_path

@pytest.fixture
def playlist_instance(temp_playlist_dir):
    """Provides a Playlist instance configured with the temp directory."""
    with patch('myapp.playlist.playlist.get_playlists_path', return_value=temp_playlist_dir):
        playlist = Playlist()
        yield playlist

@patch('myapp.playlist.playlist.validate_json', return_value=(True, None))
def test_playlist_load_valid(mock_validate, valid_playlist_file):
    with patch('myapp.playlist.playlist.get_playlists_path', return_value=os.path.dirname(valid_playlist_file)):
        playlist = Playlist(valid_playlist_file)
        mock_validate.assert_called_once() # Ensure validation was called
        assert len(playlist.get_slides()) == 2
        # --- MODIFIED: Added "text_overlay": None ---
        assert playlist.get_slide(0) == {"layers": ["image1.png"], "duration": 5, "loop_to_slide": 0, "text_overlay": None}
        # --- END MODIFIED ---
        assert playlist.file_path == valid_playlist_file
        assert playlist.get_playlists_directory() == os.path.dirname(valid_playlist_file)

def test_playlist_load_invalid_schema(invalid_schema_playlist_file):
    """Tests loading a playlist that fails schema validation."""
    with patch('myapp.playlist.playlist.get_playlists_path', return_value=os.path.dirname(invalid_schema_playlist_file)):
        with pytest.raises(ValueError, match="Playlist file has invalid format"):
            Playlist(invalid_schema_playlist_file)

def test_playlist_load_not_found(playlist_instance):
    with pytest.raises(FileNotFoundError):
        playlist_instance.load("non_existent_playlist.json")


@patch('myapp.playlist.playlist.validate_json', return_value=(True, None))
def test_playlist_save_and_load(mock_validate, playlist_instance, temp_playlist_dir):
    # Add slide without text_overlay - it should be added automatically
    playlist_instance.add_slide({"layers": ["new_image.png"], "duration": 10, "loop_to_slide": 1})
    save_path = os.path.join(temp_playlist_dir, "new_playlist.json")
    playlist_instance.save(save_path)

    loaded_playlist = Playlist(save_path)
    assert len(loaded_playlist.get_slides()) == 1
    # --- MODIFIED: Added "text_overlay": None ---
    assert loaded_playlist.get_slide(0) == {"layers": ["new_image.png"], "duration": 10, "loop_to_slide": 1, "text_overlay": None}
    # --- END MODIFIED ---
    # Check that validation was called on load (and potentially save)
    assert mock_validate.call_count >= 1


def test_playlist_add_remove_slide(playlist_instance):
    # Add slide without text_overlay
    playlist_instance.add_slide({"layers": ["image1.png"], "duration": 0, "loop_to_slide": 0})
    assert len(playlist_instance.get_slides()) == 1
    # Check if text_overlay was added
    assert playlist_instance.get_slide(0).get("text_overlay") is None
    playlist_instance.remove_slide(0)
    assert len(playlist_instance.get_slides()) == 0