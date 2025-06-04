# myapp/audio/audio_track_manager.py
import os
import json
import logging
import shutil

from ..utils.paths import get_audio_tracks_path, get_media_file_path
from ..utils.schemas import AUDIO_TRACK_METADATA_SCHEMA
from ..utils.json_validator import validate_json
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)


class AudioTrackManager:
    def __init__(self):
        self.tracks_dir = get_audio_tracks_path()
        os.makedirs(self.tracks_dir, exist_ok=True)
        logger.debug(f"AudioTrackManager initialized. Metadata directory: {self.tracks_dir}")

    def list_audio_tracks(self):
        try:
            return sorted([f.replace(".json", "") for f in os.listdir(self.tracks_dir) if f.endswith(".json")])
        except OSError as e:
            logger.error(f"Error listing audio tracks: {e}")
            return []

    def get_track_metadata_path(self, track_name: str) -> str:
        return os.path.join(self.tracks_dir, f"{track_name}.json")

    def load_track_metadata(self, track_name: str) -> dict | None:
        path = self.get_track_metadata_path(track_name)
        logger.info(f"Loading audio track metadata: {path}")
        if not os.path.exists(path):
            logger.warning(f"Metadata file not found for track: {track_name}")
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            is_valid, error = validate_json(data, AUDIO_TRACK_METADATA_SCHEMA, f"Audio Track Metadata '{track_name}'")
            if not is_valid:
                # Log detailed schema error if possible
                schema_error_details = ""
                if hasattr(error, 'message'): schema_error_details += error.message
                if hasattr(error, 'path') and error.path: schema_error_details += f" at path: {list(error.path)}"
                logger.error(f"Audio track metadata schema validation error for '{track_name}': {schema_error_details}")
                return None  # Or raise error, depending on desired strictness

            # Ensure essential fields are present with defaults if allowed by schema
            # For 'detected_duration_ms', schema allows null, so .get() is appropriate
            data["detected_duration_ms"] = data.get("detected_duration_ms")  # Ensure key exists, even if None

            logger.info(f"Successfully loaded audio track metadata: {track_name}")
            return data
        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.error(f"Failed to load or parse metadata for track '{track_name}': {e}", exc_info=True)
            return None

    def save_track_metadata(self, track_name: str, metadata: dict) -> bool:
        if not is_safe_filename_component(track_name):
            logger.error(f"Attempted to save track metadata with unsafe name: {track_name}")
            return False
        path = self.get_track_metadata_path(track_name)
        logger.info(f"Saving audio track metadata for '{track_name}' to {path}")
        try:
            # Ensure 'track_name' in metadata matches the filename for consistency
            metadata["track_name"] = track_name

            is_valid, error = validate_json(metadata, AUDIO_TRACK_METADATA_SCHEMA,
                                            f"Data for Audio Track '{track_name}' before saving")
            if not is_valid:
                schema_error_details = ""
                if hasattr(error, 'message'): schema_error_details += error.message
                if hasattr(error, 'path') and error.path: schema_error_details += f" at path: {list(error.path)}"
                logger.warning(
                    f"Audio track data validation failed before saving '{track_name}': {schema_error_details}. Attempting to save anyway.")
                # Depending on policy, you might choose not to save invalid data.

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4)
            logger.info(f"Successfully saved metadata for track '{track_name}'.")
            return True
        except IOError as e:
            logger.error(f"Error saving metadata for track '{track_name}': {e}", exc_info=True)
            return False

    def delete_track_metadata(self, track_name: str) -> bool:
        if not is_safe_filename_component(track_name):  # Check before constructing path
            logger.error(f"Attempted to delete track metadata with unsafe name: {track_name}")
            return False
        path = self.get_track_metadata_path(track_name)
        logger.info(f"Deleting audio track metadata: {path}")
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Successfully deleted metadata for track '{track_name}'.")
                return True
            except OSError as e:
                logger.error(f"Error deleting metadata for track '{track_name}': {e}", exc_info=True)
                return False
        else:
            logger.warning(f"Metadata file not found for deletion: {track_name}")
            return False  # Or True if not finding it is acceptable for deletion

    def create_metadata_from_file(self, track_name: str, source_audio_file_path: str) -> tuple[dict | None, str | None]:
        """
        Creates a metadata JSON file for a new audio track.
        Copies the source audio file to the media directory.
        Currently, duration detection is NOT implemented here and will be set to None.
        """
        safe_track_name = track_name.strip().replace(" ", "_")
        if not is_safe_filename_component(safe_track_name):
            return None, f"Track name '{safe_track_name}' contains invalid characters."

        if not os.path.exists(source_audio_file_path):
            return None, f"Source audio file not found: {source_audio_file_path}"

        # Copy file to media directory
        media_filename = os.path.basename(source_audio_file_path)
        if not is_safe_filename_component(media_filename):  # Double check media filename safety
            return None, f"Audio filename '{media_filename}' contains invalid characters."

        media_dest_path = get_media_file_path(media_filename)

        # Handle potential filename conflicts in media directory
        if os.path.exists(media_dest_path) and not os.path.samefile(source_audio_file_path, media_dest_path):
            base, ext = os.path.splitext(media_filename)
            i = 1
            while True:
                new_media_filename = f"{base}_{i:03d}{ext}"
                media_dest_path = get_media_file_path(new_media_filename)
                if not os.path.exists(media_dest_path):
                    media_filename = new_media_filename  # Update to the unique filename
                    break
                i += 1

        try:
            if not os.path.exists(media_dest_path) or not os.path.samefile(source_audio_file_path, media_dest_path):
                shutil.copy2(source_audio_file_path, media_dest_path)
                logger.info(f"Copied audio file to {media_dest_path}")
        except Exception as e:
            logger.error(f"Failed to copy audio file '{source_audio_file_path}' to media directory: {e}")
            return None, f"Could not copy audio file: {e}"

        # TODO: Implement actual audio duration detection here
        # For now, it will be None. The user will need to set it manually or it won't be available.
        detected_duration_ms = None

        metadata = {
            "track_name": safe_track_name,
            "file_path": media_filename,  # Store the (potentially modified) filename relative to media dir
            "detected_duration_ms": detected_duration_ms  # Explicitly None
        }

        if self.save_track_metadata(safe_track_name, metadata):
            return metadata, None
        else:
            return None, f"Failed to save metadata for track '{safe_track_name}'."