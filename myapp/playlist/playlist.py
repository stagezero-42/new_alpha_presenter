# myapp/playlist/playlist.py
import os
import json
import logging
from ..utils.paths import get_playlists_path
from ..utils.schemas import (
    PLAYLIST_SCHEMA, DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE,
    DEFAULT_FONT_COLOR, DEFAULT_BACKGROUND_COLOR, DEFAULT_BACKGROUND_ALPHA,
    DEFAULT_TEXT_ALIGN, DEFAULT_TEXT_VERTICAL_ALIGN, DEFAULT_FIT_TO_WIDTH
)
from ..utils.json_validator import validate_json

logger = logging.getLogger(__name__)


def get_default_text_overlay_style():
    """Returns a dictionary with default text style settings."""
    return {
        "font_family": DEFAULT_FONT_FAMILY,
        "font_size": DEFAULT_FONT_SIZE,
        "font_color": DEFAULT_FONT_COLOR,
        "background_color": DEFAULT_BACKGROUND_COLOR,
        "background_alpha": DEFAULT_BACKGROUND_ALPHA,
        "text_align": DEFAULT_TEXT_ALIGN,
        "text_vertical_align": DEFAULT_TEXT_VERTICAL_ALIGN,
        "fit_to_width": DEFAULT_FIT_TO_WIDTH,
        "paragraph_name": "",
        "start_sentence": 1,
        "end_sentence": 1,
        "sentence_timing_enabled": False,
        "auto_advance_slide": False
    }


class Playlist:
    def __init__(self, file_path=None):
        self.file_path = None
        self.slides = []
        self.playlists_dir = get_playlists_path()

        if file_path and os.path.exists(file_path):
            self.load(file_path)

    def load(self, file_path):
        logger.info(f"Loading playlist: {file_path}")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Playlist file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            is_valid, error = validate_json(data, PLAYLIST_SCHEMA, f"Playlist '{os.path.basename(file_path)}'")
            if not is_valid:
                schema_error_details = ""
                if hasattr(error, 'message'): schema_error_details += error.message
                if hasattr(error, 'path') and error.path: schema_error_details += f" at path: {list(error.path)}"
                if hasattr(error, 'instance'): schema_error_details += f" for instance: {error.instance}"
                logger.error(f"Playlist schema validation error: {schema_error_details}")
                raise ValueError(
                    f"Playlist file has invalid format: {schema_error_details or 'Unknown validation error'}")

            loaded_slides = data.get("slides", [])
            self.slides = []
            default_style_settings = get_default_text_overlay_style()

            for slide_data_from_file in loaded_slides:
                validated_slide = {
                    "layers": slide_data_from_file.get("layers", []),
                    "duration": slide_data_from_file.get("duration", 0),
                    "loop_to_slide": slide_data_from_file.get("loop_to_slide", 0),
                    "text_overlay": None,  # Default to None
                    "audio_program_name": slide_data_from_file.get("audio_program_name", None)
                }

                text_overlay_data = slide_data_from_file.get("text_overlay")
                if isinstance(text_overlay_data, dict) and text_overlay_data.get(
                        "paragraph_name"):  # Ensure it's a dict and has content
                    merged_text_overlay = default_style_settings.copy()
                    merged_text_overlay.update(text_overlay_data)
                    validated_slide["text_overlay"] = merged_text_overlay
                # If text_overlay_data is None or not a valid dict, it remains None as per validated_slide initialization

                for key, value in slide_data_from_file.items():
                    if key not in validated_slide:
                        validated_slide[key] = value

                self.slides.append(validated_slide)

            self.file_path = file_path
            logger.info(f"Successfully loaded playlist: {file_path}")

        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.error(f"Failed to load or parse playlist: {file_path}\n{e}", exc_info=True)
            raise

    def save(self, file_path_to_save_to):
        logger.info(f"Saving playlist to: {file_path_to_save_to}")
        if not file_path_to_save_to:
            raise ValueError("Playlist file path not set for saving.")

        os.makedirs(os.path.dirname(file_path_to_save_to), exist_ok=True)

        try:
            slides_to_save = []
            for slide in self.slides:
                save_slide = slide.copy()
                text_overlay_value = save_slide.get("text_overlay")
                if not isinstance(text_overlay_value, dict) or not text_overlay_value.get("paragraph_name"):
                    save_slide["text_overlay"] = None

                if not save_slide.get("audio_program_name"):
                    save_slide["audio_program_name"] = None

                slides_to_save.append(save_slide)

            playlist_data = {"slides": slides_to_save}

            is_valid, error = validate_json(playlist_data, PLAYLIST_SCHEMA, "Data before saving")
            if not is_valid:
                schema_error_details = ""
                if hasattr(error, 'message'): schema_error_details += error.message
                if hasattr(error, 'path') and error.path: schema_error_details += f" at path: {list(error.path)}"
                logger.warning(
                    f"Data validation failed before saving: {schema_error_details}. Attempting to save anyway.")

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

        text_overlay_value = slide_data.get("text_overlay")

        if isinstance(text_overlay_value, dict) and text_overlay_value.get("paragraph_name"):
            default_style = get_default_text_overlay_style()
            para_name = text_overlay_value.get("paragraph_name", "")
            merged_overlay = {**default_style, **text_overlay_value}
            merged_overlay["paragraph_name"] = para_name
            slide_data["text_overlay"] = merged_overlay
        else:
            slide_data["text_overlay"] = None  # Handles None, not a dict, or dict without para_name

        if "audio_program_name" not in slide_data or not slide_data["audio_program_name"]:
            slide_data["audio_program_name"] = None

        self.slides.append(slide_data)

    def update_slide(self, index, slide_data):
        logger.debug(f"Updating slide at index {index} with: {slide_data}")
        if 0 <= index < len(self.slides):
            text_overlay_value = slide_data.get("text_overlay")

            if isinstance(text_overlay_value, dict) and text_overlay_value.get("paragraph_name"):
                default_style = get_default_text_overlay_style()
                para_name = text_overlay_value.get("paragraph_name", "")
                merged_overlay = {**default_style, **text_overlay_value}
                merged_overlay["paragraph_name"] = para_name
                slide_data["text_overlay"] = merged_overlay
            else:
                slide_data["text_overlay"] = None  # Handles None, not a dict, or dict without para_name

            if "audio_program_name" not in slide_data or not slide_data["audio_program_name"]:
                slide_data["audio_program_name"] = None

            self.slides[index] = slide_data
        else:
            logger.warning(f"Attempted to update slide at invalid index: {index}")

    def remove_slide(self, index):
        logger.debug(f"Removing slide at index: {index}")
        if 0 <= index < len(self.slides):
            del self.slides[index]
        else:
            logger.warning(f"Attempted to remove slide at invalid index: {index}")

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
        self.slides = []
        default_style = get_default_text_overlay_style()  # Not strictly needed here if add_slide logic is robust
        for slide_entry in slides_data:  # Make a copy to avoid modifying original list items if they are refs
            current_slide_data = slide_entry.copy()

            text_overlay_value = current_slide_data.get("text_overlay")
            if isinstance(text_overlay_value, dict) and text_overlay_value.get("paragraph_name"):
                para_name = text_overlay_value.get("paragraph_name", "")
                # Ensure all default style keys are present
                merged_overlay = get_default_text_overlay_style()  # Start with fresh defaults
                merged_overlay.update(text_overlay_value)  # Apply overrides from loaded data
                merged_overlay["paragraph_name"] = para_name  # Re-ensure this specific one
                current_slide_data["text_overlay"] = merged_overlay
            else:
                current_slide_data["text_overlay"] = None

            if "audio_program_name" not in current_slide_data or not current_slide_data["audio_program_name"]:
                current_slide_data["audio_program_name"] = None

            self.slides.append(current_slide_data)

    def get_playlists_directory(self):
        return self.playlists_dir