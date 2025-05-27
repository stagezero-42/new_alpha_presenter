# myapp/playlist/playlist.py
import os
import json
from ..utils.paths import get_playlists_path
# --- NEW IMPORTS ---
from ..utils.schemas import PLAYLIST_SCHEMA
from ..utils.json_validator import validate_json
# --- END NEW IMPORTS ---


class Playlist:
    def __init__(self, file_path=None):
        self.file_path = None
        self.slides = []
        self.playlists_dir = get_playlists_path() #

        if file_path and os.path.exists(file_path):
            self.load(file_path)

    def load(self, file_path):
        """Loads a playlist from a specific .json file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Playlist file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # --- NEW: Validate the loaded data ---
            is_valid, error = validate_json(data, PLAYLIST_SCHEMA, f"Playlist '{os.path.basename(file_path)}'")
            if not is_valid:
                raise ValueError(f"Playlist file has invalid format: {error.message}")
            # --- END NEW ---

            # Ensure 'slides' exists and apply defaults if needed
            loaded_slides = data.get("slides", [])
            self.slides = []
            for slide in loaded_slides:
                 # Ensure each slide has all keys, even if schema has defaults
                 validated_slide = {
                     "layers": slide.get("layers", []),
                     "duration": slide.get("duration", 0),
                     "loop_to_slide": slide.get("loop_to_slide", 0)
                 }
                 # Copy any other extra properties (future-proofing)
                 validated_slide.update({k: v for k, v in slide.items() if k not in validated_slide})
                 self.slides.append(validated_slide)

            self.file_path = file_path

        except (json.JSONDecodeError, IOError, ValueError) as e: # Added ValueError
            raise ValueError(f"Failed to load or parse playlist: {file_path}\n{e}")

    def save(self, file_path_to_save_to):
        """Saves the current playlist data to a specific .json file."""
        if not file_path_to_save_to:
            raise ValueError("Playlist file path not set for saving.")

        os.makedirs(os.path.dirname(file_path_to_save_to), exist_ok=True)

        try:
            # --- Ensure data matches schema before saving (optional but good) ---
            playlist_data = {"slides": self.slides}
            is_valid, _ = validate_json(playlist_data, PLAYLIST_SCHEMA, "Data before saving")
            if not is_valid:
                print("Warning: Data might not perfectly match schema before saving, but attempting anyway.")
            # --- End Check ---

            with open(file_path_to_save_to, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, indent=4)
            self.file_path = file_path_to_save_to
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