# myapp/playlist/playlist.py
import os
import json
from ..utils.paths import get_playlists_path

class Playlist:
    def __init__(self, file_path=None):
        self.file_path = None
        self.slides = []
        self.playlists_dir = get_playlists_path() # Base dir for all playlists

        if file_path and os.path.exists(file_path):
            self.load(file_path)

    def load(self, file_path):
        """Loads a playlist from a specific .json file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Playlist file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.slides = data.get("slides", [])
            self.file_path = file_path # Store the full path

        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to load or parse playlist: {file_path}\n{e}")

    def save(self, file_path_to_save_to):
        """Saves the current playlist data to a specific .json file."""
        if not file_path_to_save_to:
            raise ValueError("Playlist file path not set for saving.")

        # Ensure the target directory exists (should already by playlists_dir)
        os.makedirs(os.path.dirname(file_path_to_save_to), exist_ok=True)

        try:
            with open(file_path_to_save_to, 'w', encoding='utf-8') as f:
                json.dump({"slides": self.slides}, f, indent=4)
            self.file_path = file_path_to_save_to # Update current path
            return True
        except IOError as e:
            print(f"Error saving playlist to {file_path_to_save_to}: {e}")
            return False

    def add_slide(self, slide_data):
        self.slides.append(slide_data)

    def remove_slide(self, index):
        if 0 <= index < len(self.slides):
            del self.slides[index]

    def update_slide(self, index, slide_data):
        if 0 <= index < len(self.slides):
            self.slides[index] = slide_data

    def get_slide(self, index):
        return self.slides[index] if 0 <= index < len(self.slides) else None

    def get_slides(self):
        return self.slides

    def set_slides(self, slides_data):
        self.slides = list(slides_data)

    def get_playlists_directory(self):
        return self.playlists_dir