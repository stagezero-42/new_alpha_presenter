# myapp/audio/audio_track_manager.py
import os
import json
import logging
from mutagen import File as MutagenFile  # For reading audio metadata
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis

from ..utils.paths import get_audio_tracks_metadata_path, get_media_file_path
from ..utils.schemas import AUDIO_TRACK_METADATA_SCHEMA
from ..utils.json_validator import validate_json
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)


class AudioTrackManager:
    """Manages loading, saving, and listing Audio Track Metadata JSON files."""

    def __init__(self, audio_tracks_dir=None):
        self.audio_tracks_dir = audio_tracks_dir if audio_tracks_dir is not None else get_audio_tracks_metadata_path()
        os.makedirs(self.audio_tracks_dir, exist_ok=True)
        logger.debug(f"AudioTrackManager initialized. Metadata directory: {self.audio_tracks_dir}")

    def _get_metadata_file_path(self, track_name):
        return os.path.join(self.audio_tracks_dir, f"{track_name}.json")

    def detect_audio_duration(self, media_file_path_abs: str) -> int | None:
        """
        Detects the duration of an audio file in milliseconds using mutagen.
        Returns None if duration cannot be detected or an error occurs.
        """
        if not os.path.exists(media_file_path_abs):
            logger.error(f"Audio file not found for duration detection: {media_file_path_abs}")
            return None
        try:
            audio = MutagenFile(media_file_path_abs, easy=True)
            if audio is not None and audio.info is not None and hasattr(audio.info, 'length'):
                duration_seconds = audio.info.length
                logger.info(f"Detected duration for '{media_file_path_abs}': {duration_seconds:.2f}s")
                return int(duration_seconds * 1000)  # Convert to milliseconds
            else:
                # Fallback for specific types if easy=True didn't work well for info.length
                # This part might need refinement based on the exact types of audio files used.
                if media_file_path_abs.lower().endswith(".mp3"):
                    audio_specific = MP3(media_file_path_abs)
                    return int(audio_specific.info.length * 1000)
                elif media_file_path_abs.lower().endswith(".wav"):
                    audio_specific = WAVE(media_file_path_abs)
                    return int(audio_specific.info.length * 1000)
                elif media_file_path_abs.lower().endswith(".flac"):
                    audio_specific = FLAC(media_file_path_abs)
                    return int(audio_specific.info.length * 1000)
                elif media_file_path_abs.lower().endswith((".ogg", ".oga")):
                    audio_specific = OggVorbis(media_file_path_abs)
                    return int(audio_specific.info.length * 1000)

                logger.warning(
                    f"Could not determine duration for '{media_file_path_abs}' using mutagen. Audio info: {audio.info if audio else 'None'}")
                return None
        except Exception as e:
            logger.error(f"Error detecting duration for '{media_file_path_abs}' with mutagen: {e}", exc_info=True)
            return None

    def load_track_metadata(self, track_name):
        if not is_safe_filename_component(f"{track_name}.json"):
            logger.error(f"Attempted to load audio track metadata with unsafe name: {track_name}")
            return None

        file_path = self._get_metadata_file_path(track_name)
        logger.info(f"Loading audio track metadata: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"Audio track metadata file not found: {file_path}")
            raise FileNotFoundError(f"Audio track metadata file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            is_valid, error = validate_json(data, AUDIO_TRACK_METADATA_SCHEMA, f"Audio Track Metadata '{track_name}'")
            if not is_valid:
                msg = error.message if error else 'Unknown validation error'
                logger.error(f"Audio track metadata file '{track_name}' has invalid format: {msg}")
                raise ValueError(f"Audio track metadata file has invalid format: {msg}")

            if data.get("track_name") != track_name:
                logger.warning(
                    f"Track name '{data.get('track_name')}' in metadata file does not match filename '{track_name}'. Using filename.")
                data["track_name"] = track_name

            media_file_actual_path = get_media_file_path(data.get("file_path", ""))
            if not os.path.exists(media_file_actual_path):
                logger.warning(
                    f"Actual audio media file '{data.get('file_path')}' not found at '{media_file_actual_path}' for track '{track_name}'. Duration might be stale if file was moved/deleted.")
            elif data.get("detected_duration_ms") is None:  # If duration was never detected or null
                logger.info(f"Detected duration is null for {track_name}, attempting to re-detect.")
                new_duration = self.detect_audio_duration(media_file_actual_path)
                if new_duration is not None:
                    data["detected_duration_ms"] = new_duration
                    # Optionally re-save the metadata file here if duration was updated
                    # self.save_track_metadata(track_name, data)
                    logger.info(f"Updated detected duration for {track_name} to {new_duration}ms.")
                else:
                    logger.warning(f"Still could not detect duration for {track_name}.")

            logger.info(f"Successfully loaded audio track metadata: {track_name}")
            return data

        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.error(f"Failed to load or parse audio track metadata: {file_path}\n{e}", exc_info=True)
            raise ValueError(f"Failed to load or parse audio track metadata: {file_path}\n{e}")

    def save_track_metadata(self, track_name, data):
        if not is_safe_filename_component(f"{track_name}.json"):
            logger.error(f"Attempted to save audio track metadata with unsafe name: {track_name}")
            return False

        file_path = self._get_metadata_file_path(track_name)
        logger.info(f"Saving audio track metadata to: {file_path}")

        if data.get("track_name") != track_name:
            logger.warning(
                f"Data track_name '{data.get('track_name')}' differs from save name '{track_name}'. Saving with '{track_name}'.")
            data["track_name"] = track_name

        # Perform schema validation EARLIER
        is_valid, error = validate_json(data, AUDIO_TRACK_METADATA_SCHEMA, f"Audio Track Metadata for '{track_name}'")
        if not is_valid:
            msg = error.message if error else 'Unknown validation error'
            logger.error(f"Cannot save audio track metadata '{track_name}', data invalid (schema): {msg}")
            return False

        media_file_in_data = data.get("file_path") # Now we know file_path is a string if schema passed
        if media_file_in_data:
            if not os.path.exists(get_media_file_path(media_file_in_data)):
                logger.warning(
                    f"Media file '{media_file_in_data}' referenced in metadata for '{track_name}' does not exist in media assets. Saving metadata anyway.")
        else:
            # This case should ideally be caught by schema validation if file_path is required
            logger.error(f"Cannot save metadata for '{track_name}': 'file_path' field is missing or invalid in data after schema validation (this should not happen if schema requires it).")
            return False

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Audio track metadata '{track_name}' saved successfully.")
            return True
        except IOError as e:
            logger.error(f"Error saving audio track metadata to {file_path}: {e}", exc_info=True)
            return False

    def list_audio_tracks(self):
        """Lists all available audio track metadata names."""
        try:
            files = [f for f in os.listdir(self.audio_tracks_dir)
                     if os.path.isfile(os.path.join(self.audio_tracks_dir, f)) and f.lower().endswith('.json')]
            names = [os.path.splitext(f)[0] for f in files]
            logger.debug(f"Found audio track metadata: {names}")
            return names
        except OSError as e:
            logger.error(f"Error listing audio track metadata in {self.audio_tracks_dir}: {e}", exc_info=True)
            return []

    def delete_track_metadata(self, track_name):
        if not is_safe_filename_component(f"{track_name}.json"):
            logger.error(f"Attempted to delete audio track metadata with unsafe name: {track_name}")
            return False

        file_path = self._get_metadata_file_path(track_name)
        logger.warning(f"Attempting to delete audio track metadata: {file_path}")
        # Note: This does NOT delete the actual audio file from assets/media, only its metadata.
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Audio track metadata '{track_name}' deleted.")
            else:
                logger.info(f"Audio track metadata '{track_name}' did not exist, nothing to delete.")
            return True
        except OSError as e:
            logger.error(f"Error deleting audio track metadata {file_path}: {e}", exc_info=True)
            return False