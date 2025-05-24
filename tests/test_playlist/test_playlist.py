# tests/test_playlist/test_playlist.py
import pytest
import os
import json
import shutil
from myapp.playlist.playlist import Playlist, get_base_path

@pytest.fixture
def temp_playlist_dir(tmp_path):
    """Creates a temporary directory for playlists and media."""
    playlist_dir = tmp_path / "playlists"
    playlist_dir.mkdir()
    return playlist_dir

@pytest.fixture
def valid_playlist_file(temp_playlist_dir):
    """Creates a valid playlist file and returns its path."""
    playlist_content = {"slides": [{"layers": ["image1.png"]}, {"layers": ["image2.png"]}]}
    playlist_path = temp_playlist_dir / "test_playlist.json"
    with open(playlist_path, "w") as f:
        json.dump(playlist_content, f)
    return playlist_path

def test_playlist_load_valid(valid_playlist_file):
    playlist = Playlist(valid_playlist_file)
    assert len(playlist.get_slides()) == 2
    assert playlist.get_slide(0) == {"layers": ["image1.png"]}
    assert playlist.get_media_dir() == os.path.join(os.path.dirname(valid_playlist_file), "media_files")

def test_playlist_load_not_found():
    with pytest.raises(FileNotFoundError):
        Playlist("non_existent_playlist.json")

def test_playlist_save_and_load(temp_playlist_dir):
    playlist = Playlist()
    playlist.add_slide({"layers": ["new_image.png"]})
    save_path = temp_playlist_dir / "new_playlist.json"
    playlist.save(save_path)

    loaded_playlist = Playlist(save_path)
    assert len(loaded_playlist.get_slides()) == 1
    assert loaded_playlist.get_slide(0) == {"layers": ["new_image.png"]}

def test_playlist_add_remove_slide():
    playlist = Playlist()
    playlist.add_slide({"layers": ["image1.png"]})
    assert len(playlist.get_slides()) == 1
    playlist.remove_slide(0)
    assert len(playlist.get_slides()) == 0

def test_playlist_copy_media_file(temp_playlist_dir):
    playlist = Playlist()
    media_dir = temp_playlist_dir / "media"
    media_dir.mkdir()
    playlist.set_media_dir(media_dir)

    source_file = temp_playlist_dir / "source_image.png"
    source_file.touch()

    playlist.copy_media_file(source_file)
    assert os.path.exists(media_dir / "source_image.png")