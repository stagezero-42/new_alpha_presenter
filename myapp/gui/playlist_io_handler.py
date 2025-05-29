# myapp/gui/playlist_io_handler.py
import logging
from PySide6.QtWidgets import QMessageBox

from ..settings.settings_manager import SettingsManager
from ..utils.paths import get_playlists_path
from .file_dialog_helpers import get_themed_open_filename
from ..playlist.playlist import Playlist # Needed for a quick check

logger = logging.getLogger(__name__)

class PlaylistIOHandler:
    """
    Handles loading playlist paths via dialogs or settings.
    It does *not* load the playlist into ControlWindow but provides the path.
    """

    def __init__(self, parent_window, settings_manager: SettingsManager):
        """
        Initializes the PlaylistIOHandler.

        Args:
            parent_window: The parent QWidget, used for dialogs and message boxes.
            settings_manager: An instance of SettingsManager.
        """
        self.parent = parent_window
        self.settings_manager = settings_manager
        logger.debug("PlaylistIOHandler initialized.")

    def prompt_load_playlist(self) -> str | None:
        """
        Opens a file dialog for the user to select a playlist file.
        Performs a basic check to see if it can be loaded before returning.

        Returns:
            The full path to the selected playlist file, or None if cancelled
            or an immediate error occurs.
        """
        logger.debug("Opening load playlist dialog...")
        default_dir = get_playlists_path()
        file_path = get_themed_open_filename(
            self.parent, "Open Playlist", default_dir, "JSON Files (*.json)"
        )

        if not file_path:
            logger.info("Load playlist dialog cancelled.")
            return None

        # Optional: Perform a quick validation check here
        try:
            temp_playlist = Playlist(file_path) # This tries to load and validate
            logger.info(f"User selected valid-looking playlist: {file_path}")
            return file_path
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Selected file '{file_path}' failed to load: {e}", exc_info=True)
            QMessageBox.critical(self.parent, "Load Error", f"Failed to load playlist: {e}")
            return None

    def get_last_playlist_path(self) -> str | None:
        """
        Retrieves the path of the last used playlist from settings.

        Returns:
            The path if it exists and is valid, otherwise None.
        """
        last_path = self.settings_manager.get_current_playlist()
        if last_path:
            logger.info(f"Found last used playlist in settings: {last_path}")
            return last_path
        else:
            logger.info("No last playlist found in settings.")
            return None