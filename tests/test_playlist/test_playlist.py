# tests/test_playlist/test_playlist.py
import pytest
import os
import json
import shutil
from unittest.mock import patch # Make sure patch is imported
from myapp.playlist.playlist import Playlist

@pytest.fixture
def temp_playlist_dir(tmp_path):
    """Creates a temporary directory for playlists."""
    playlist_dir = tmp_path / "playlists"
    playlist_dir.mkdir()
    yield str(playlist_dir) # Yield as string


@pytest.fixture
def valid_playlist_file(temp_playlist_dir):
    """Creates a valid playlist file and returns its path."""
    playlist_content = {"slides": [{"layers": ["image1.png"]}, {"layers": ["image2.png"]}]}
    playlist_path = os.path.join(temp_playlist_dir, "test_playlist.json")
    with open(playlist_path, "w") as f:
        json.dump(playlist_content, f)
    return playlist_path


@pytest.fixture
def playlist_instance(temp_playlist_dir):
    """Provides a Playlist instance configured with the temp directory."""
    with patch('myapp.playlist.playlist.get_playlists_path', return_value=temp_playlist_dir):
        playlist = Playlist()
        yield playlist


def test_playlist_load_valid(valid_playlist_file):
    with patch('myapp.playlist.playlist.get_playlists_path', return_value=os.path.dirname(valid_playlist_file)):
        playlist = Playlist(valid_playlist_file)
        assert len(playlist.get_slides()) == 2
        assert playlist.get_slide(0) == {"layers": ["image1.png"]}
        assert playlist.file_path == valid_playlist_file
        assert playlist.get_playlists_directory() == os.path.dirname(valid_playlist_file)


# --- MODIFIED: Call load() directly ---
def test_playlist_load_not_found(playlist_instance):
    with pytest.raises(FileNotFoundError):
        playlist_instance.load("non_existent_playlist.json")
# --- END MODIFIED ---


def test_playlist_save_and_load(playlist_instance, temp_playlist_dir):
    playlist_instance.add_slide({"layers": ["new_image.png"]})
    save_path = os.path.join(temp_playlist_dir, "new_playlist.json")
    playlist_instance.save(save_path)

    loaded_playlist = Playlist(save_path)
    assert len(loaded_playlist.get_slides()) == 1
    assert loaded_playlist.get_slide(0) == {"layers": ["new_image.png"]}


def test_playlist_add_remove_slide(playlist_instance):
    playlist_instance.add_slide({"layers": ["image1.png"]})
    assert len(playlist_instance.get_slides()) == 1
    playlist_instance.remove_slide(0)
    assert len(playlist_instance.get_slides()) == 0