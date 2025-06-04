# myapp/playlist/playlist.py
import os
import json
import logging
from ..utils.paths import get_playlists_path
from ..utils.schemas import (
    PLAYLIST_SCHEMA, DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE,
    DEFAULT_FONT_COLOR, DEFAULT_BACKGROUND_COLOR, DEFAULT_BACKGROUND_ALPHA,
    DEFAULT_TEXT_ALIGN, DEFAULT_TEXT_VERTICAL_ALIGN, DEFAULT_FIT_TO_WIDTH,
    DEFAULT_AUDIO_PROGRAM_VOLUME
)
from ..utils.json_validator import validate_json

logger = logging.getLogger(__name__)


def get_default_text_overlay_style():
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


def get_default_slide_audio_settings():
    return {
        "audio_program_name": None,
        "loop_audio_program": False,
        "audio_intro_delay_ms": 0,
        "audio_outro_duration_ms": 0,
        "audio_program_volume": DEFAULT_AUDIO_PROGRAM_VOLUME
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
            default_text_style = get_default_text_overlay_style()
            default_audio_settings = get_default_slide_audio_settings()

            for slide_data_from_file in loaded_slides:
                # Start with all audio defaults
                validated_slide = {
                    "layers": slide_data_from_file.get("layers", []),
                    "duration": slide_data_from_file.get("duration", 0),
                    "loop_to_slide": slide_data_from_file.get("loop_to_slide", 0),
                    "text_overlay": None,
                    **default_audio_settings  # Apply all audio defaults first
                }
                # Then update with specifics from file if they exist
                for key in default_audio_settings.keys():
                    if key in slide_data_from_file:
                        validated_slide[key] = slide_data_from_file[key]

                text_overlay_data = slide_data_from_file.get("text_overlay")
                if isinstance(text_overlay_data, dict):
                    merged_text_overlay = default_text_style.copy()
                    merged_text_overlay.update(text_overlay_data)
                    validated_slide["text_overlay"] = merged_text_overlay
                elif text_overlay_data is None:
                    validated_slide["text_overlay"] = None

                for key, value in slide_data_from_file.items():
                    if key not in validated_slide:  # Add any other custom properties
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
            default_audio_settings = get_default_slide_audio_settings()
            for slide in self.slides:
                save_slide = slide.copy()
                if "text_overlay" in save_slide:
                    overlay = save_slide["text_overlay"]
                    if overlay is None or not overlay.get("paragraph_name"):
                        if "text_overlay" in save_slide:
                            del save_slide["text_overlay"]

                # Clean up default audio settings before saving
                has_audio_program = bool(save_slide.get("audio_program_name"))

                for key, default_value in default_audio_settings.items():
                    # Always remove audio settings if no audio program, or if they match default
                    if not has_audio_program or save_slide.get(key) == default_value:
                        if key in save_slide:
                            del save_slide[key]

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
        default_audio_settings = get_default_slide_audio_settings()

        if "text_overlay" in slide_data and isinstance(slide_data["text_overlay"], dict) and slide_data[
            "text_overlay"].get("paragraph_name"):
            default_style = get_default_text_overlay_style()
            para_name = slide_data["text_overlay"].get("paragraph_name", "")
            merged_overlay = {**default_style, **slide_data["text_overlay"]}
            merged_overlay["paragraph_name"] = para_name
            slide_data["text_overlay"] = merged_overlay
        elif "text_overlay" not in slide_data or not isinstance(slide_data.get("text_overlay"),
                                                                dict) or not slide_data.get("text_overlay", {}).get(
            "paragraph_name"):
            slide_data["text_overlay"] = None

        for key, default_value in default_audio_settings.items():
            if key not in slide_data:
                slide_data[key] = default_value

        self.slides.append(slide_data)

    def update_slide(self, index, slide_data):
        logger.debug(f"Updating slide at index {index} with: {slide_data}")
        if 0 <= index < len(self.slides):
            default_audio_settings = get_default_slide_audio_settings()

            if "text_overlay" in slide_data and isinstance(slide_data["text_overlay"], dict) and slide_data[
                "text_overlay"].get("paragraph_name"):
                default_style = get_default_text_overlay_style()
                para_name = slide_data["text_overlay"].get("paragraph_name", "")
                merged_overlay = {**default_style, **slide_data["text_overlay"]}
                merged_overlay["paragraph_name"] = para_name
                slide_data["text_overlay"] = merged_overlay
            elif "text_overlay" in slide_data and slide_data["text_overlay"] is None:
                pass
            elif "text_overlay" not in slide_data or not isinstance(slide_data.get("text_overlay"),
                                                                    dict) or not slide_data.get("text_overlay", {}).get(
                "paragraph_name"):
                slide_data["text_overlay"] = None

            for key, default_value in default_audio_settings.items():
                slide_data.setdefault(key, default_value)  # Ensure all audio keys exist

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
        default_text_style = get_default_text_overlay_style()
        default_audio_settings = get_default_slide_audio_settings()

        for slide in slides_data:
            # Ensure text_overlay structure
            if "text_overlay" in slide and isinstance(slide["text_overlay"], dict) and slide["text_overlay"].get(
                    "paragraph_name"):
                para_name = slide["text_overlay"].get("paragraph_name", "")
                merged_overlay = {**default_text_style, **slide["text_overlay"]}
                merged_overlay["paragraph_name"] = para_name
                slide["text_overlay"] = merged_overlay
            elif "text_overlay" not in slide or slide["text_overlay"] is None or not slide.get("text_overlay", {}).get(
                    "paragraph_name"):
                slide["text_overlay"] = None

            # Ensure all audio settings default if not present
            for key, default_value in default_audio_settings.items():
                slide.setdefault(key, default_value)
            self.slides.append(slide)

    def get_playlists_directory(self):
        return self.playlists_dir

    def insert_slide(self, index, slide_data):
        """Inserts a slide at a specific index."""
        logger.debug(f"Inserting slide at index {index}: {slide_data}")
        default_audio_settings = get_default_slide_audio_settings()

        # Ensure text_overlay structure for the new slide
        if "text_overlay" in slide_data and isinstance(slide_data["text_overlay"], dict) and slide_data[
            "text_overlay"].get("paragraph_name"):
            default_style = get_default_text_overlay_style()
            para_name = slide_data["text_overlay"].get("paragraph_name", "")
            merged_overlay = {**default_style, **slide_data["text_overlay"]}
            merged_overlay["paragraph_name"] = para_name
            slide_data["text_overlay"] = merged_overlay
        else:  # Handles None, missing, or invalid text_overlay
            slide_data["text_overlay"] = None

        # Ensure all audio settings keys are present, defaulting if necessary
        for key, default_value in default_audio_settings.items():
            slide_data.setdefault(key, default_value)

        if 0 <= index <= len(self.slides):
            self.slides.insert(index, slide_data)
        else:  # Append if index is out of bounds (though typically should be valid)
            self.slides.append(slide_data)
            logger.warning(f"Insert slide index {index} out of bounds, appended instead.")