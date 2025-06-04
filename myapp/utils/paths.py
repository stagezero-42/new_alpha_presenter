# myapp/utils/paths.py
import os
import sys
import logging

logger = logging.getLogger(__name__)


def get_app_root_path():
    """Gets the root directory of the application."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_assets_path():
    """Gets the path to the main 'assets' directory."""
    return os.path.join(get_app_root_path(), "assets")


def get_media_path():
    """Gets the path to the 'media' directory inside 'assets'."""
    return os.path.join(get_assets_path(), "media")


def get_media_file_path(filename: str) -> str:
    """Gets the full path to a specific file within the 'media' directory."""
    return os.path.join(get_media_path(), filename)


def get_playlists_path():
    """Gets the path to the 'playlists' directory inside 'assets'."""
    return os.path.join(get_assets_path(), "playlists")


def get_playlist_file_path(filename: str) -> str:
    """Gets the full path to a specific file within the 'playlists' directory."""
    return os.path.join(get_playlists_path(), filename)


def get_texts_path():
    """Gets the path to the 'texts' directory inside 'assets'."""
    return os.path.join(get_assets_path(), "texts")


def get_text_file_path(filename: str) -> str:
    """Gets the full path to a specific file within the 'texts' directory."""
    return os.path.join(get_texts_path(), filename)


def get_settings_path():
    """Gets the path to the 'settings' directory inside 'assets'."""
    return os.path.join(get_assets_path(), "settings")


def get_settings_file_path(filename: str = "settings.json") -> str:
    """Gets the full path to the settings file."""
    return os.path.join(get_settings_path(), filename)


def get_audio_programs_path():
    """Gets the path to the 'audio_programs' directory inside 'assets'."""
    return os.path.join(get_assets_path(), "audio_programs")


def get_audio_program_file_path(filename: str) -> str:
    """Gets the full path to a specific file within the 'audio_programs' directory."""
    return os.path.join(get_audio_programs_path(), filename)


def get_audio_tracks_path():
    """Gets the path to the 'audio_tracks' (metadata) directory inside 'assets'."""
    return os.path.join(get_assets_path(), "audio_tracks")


def get_audio_track_file_path(filename: str) -> str:
    """Gets the full path to a specific file within the 'audio_tracks' (metadata) directory."""
    return os.path.join(get_audio_tracks_path(), filename)


def get_icons_path():
    """Gets the path to the 'icons' directory inside 'assets'."""
    return os.path.join(get_assets_path(), "icons")


def get_log_file_path(filename: str = "alphapresenter.log") -> str:
    """Gets the full path for the application log file in the app root."""
    return os.path.join(get_app_root_path(), filename)


def get_icon_file_path(icon_filename: str) -> str | None:
    """
    Constructs the full path to an icon file within the local 'assets/icons' directory.
    """
    local_icon_path = os.path.join(get_icons_path(), icon_filename)
    if os.path.exists(local_icon_path):
        return local_icon_path

    # Fallback or more complex system icon lookup could be added here if desired,
    # but for now, we primarily rely on local assets.
    logger.warning(f"Icon '{icon_filename}' not found in {get_icons_path()}.")
    return None


def ensure_assets_folders_exist():
    """
    Ensures that all necessary asset subdirectories are created.
    This should be called once at application startup.
    """
    paths_to_ensure = [
        get_assets_path(),  # Main assets folder
        get_media_path(),
        get_playlists_path(),
        get_texts_path(),
        get_settings_path(),
        get_audio_programs_path(),
        get_audio_tracks_path(),
        get_icons_path()  # For icons
    ]
    for path in paths_to_ensure:
        try:
            os.makedirs(path, exist_ok=True)
            logger.debug(f"Ensured asset folder exists: {path}")
        except OSError as e:
            # Log an error but try to continue; essential paths might cause app failure later if not creatable.
            logger.error(f"Could not create asset folder {path}: {e}", exc_info=True)
            # Depending on the importance, you might want to raise an exception here
            # or handle it more gracefully in the main application.