# myapp/playlist/playlist.py
import os
import json
import logging  # Import logging
from ..utils.paths import get_playlists_path
from ..utils.schemas import PLAYLIST_SCHEMA
from ..utils.json_validator import validate_json

logger = logging.getLogger(__name__)  # Get logger for this module

class Playlist:
    def __init__(self, file_path=None):
        self.file_path = None
        self.slides = []
        self.playlists_dir = get_playlists_path()

        if file_path and os.path.exists(file_path):
            self.load(file_path)

    def load(self, file_path):
        """Loads a playlist from a specific .json file."""
        logger.info(f"Loading playlist: {file_path}")
        if not os.path.exists(file_path):
            logger.error(f"Playlist file not found: {file_path}")
            raise FileNotFoundError(f"Playlist file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            is_valid, error = validate_json(data, PLAYLIST_SCHEMA, f"Playlist '{os.path.basename(file_path)}'")
            if not is_valid:
                logger.error(f"Playlist file has invalid format: {error.message}")
                raise ValueError(f"Playlist file has invalid format: {error.message}")

            loaded_slides = data.get("slides", [])
            self.slides = []
            for slide in loaded_slides:
                 validated_slide = {
                     "layers": slide.get("layers", []),
                     "duration": slide.get("duration", 0),
                     "loop_to_slide": slide.get("loop_to_slide", 0)
                 }
                 validated_slide.update({k: v for k, v in slide.items() if k not in validated_slide})
                 self.slides.append(validated_slide)

            self.file_path = file_path
            logger.info(f"Successfully loaded playlist: {file_path}")

        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.error(f"Failed to load or parse playlist: {file_path}\n{e}", exc_info=True)
            raise ValueError(f"Failed to load or parse playlist: {file_path}\n{e}")

    def save(self, file_path_to_save_to):
        """Saves the current playlist data to a specific .json file."""
        logger.info(f"Saving playlist to: {file_path_to_save_to}")
        if not file_path_to_save_to:
            logger.error("Playlist file path not set for saving.")
            raise ValueError("Playlist file path not set for saving.")

        os.makedirs(os.path.dirname(file_path_to_save_to), exist_ok=True)

        try:
            playlist_data = {"slides": self.slides}
            is_valid, _ = validate_json(playlist_data, PLAYLIST_SCHEMA, "Data before saving")
            if not is_valid:
                logger.warning("Data might not perfectly match schema before saving, but attempting anyway.")

            with open(file_path_to_save_to, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, indent=4)
            self.file_path = file_path_to_save_to
            logger.info(f"Playlist saved successfully to {file_path_to_save_to}")
            return True
        except IOError as e:
            logger.error(f"Error saving playlist to {file_path_to_save_to}: {e}", exc_info=True)
            return False

    def add_slide(self, slide_data):
        logger.debug(f"Adding slide: {slide_data}")
        self.slides.append(slide_data)

    def remove_slide(self, index):
        logger.debug(f"Removing slide at index: {index}")
        if 0 <= index < len(self.slides):
            del self.slides[index]
        else:
            logger.warning(f"Attempted to remove slide at invalid index: {index}")

    def update_slide(self, index, slide_data):
        logger.debug(f"Updating slide at index {index} with: {slide_data}")
        if 0 <= index < len(self.slides):
            self.slides[index] = slide_data
        else:
            logger.warning(f"Attempted to update slide at invalid index: {index}")

    def get_slide(self, index):
        if 0 <= index < len(self.slides):
            return self.slides[index]
        else:
            logger.warning(f"Attempted to get slide at invalid index: {index}")
            return None

    def get_slides(self):
        return self.slides

    def set_slides(self, slides_data):
        logger.debug("Setting slides.")
        self.slides = list(slides_data)

    def get_playlists_directory(self):
        return self.playlists_dir