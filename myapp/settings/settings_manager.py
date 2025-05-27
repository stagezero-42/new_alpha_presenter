# myapp/settings/settings_manager.py
import json
import os
import logging # Import logging
from ..utils.paths import get_settings_file_path
from ..utils.schemas import SETTINGS_SCHEMA
from ..utils.json_validator import validate_json

logger = logging.getLogger(__name__) # Get logger for this module

class SettingsManager:
    def __init__(self):
        self.settings_file = get_settings_file_path()
        self.settings = self._load_defaults()
        self.load_settings()

    def _load_defaults(self):
        """Returns the default settings dictionary."""
        return {
            "current_playlist_path": None,
            "keybindings": {
                "next": ["Right", "Down", "PgDown"],
                "prev": ["Left", "Up", "PgUp"],
                "go": ["Space"],
                "clear": ["Escape"],
                "quit": ["Ctrl+Q"],
                "load": ["Ctrl+L"],
                "edit": ["Ctrl+E"]
            },
            # --- NEW LOGGING DEFAULTS ---
            "log_level": "INFO",
            "log_to_file": False,
            "log_file_path": "alphapresenter.log"
            # --- END NEW LOGGING DEFAULTS ---
        }

    def load_settings(self):
        """Loads settings from the JSON file, merging with defaults."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)

                is_valid, _ = validate_json(loaded_settings, SETTINGS_SCHEMA, "Settings file")
                if not is_valid:
                    logger.warning("Settings file format is not fully valid. "
                                   "Attempting to load usable parts.")

                defaults = self._load_defaults()
                self.settings = defaults

                if isinstance(loaded_settings, dict):
                    # --- MODIFIED: Load all known keys ---
                    for key in self.settings.keys():
                        if key in loaded_settings:
                             # Basic type check before assigning, could be more robust
                             if key == "keybindings" and isinstance(loaded_settings[key], dict):
                                 # Special handling for keybindings (already exists)
                                 for k_key in self.settings["keybindings"].keys():
                                     if k_key in loaded_settings["keybindings"]:
                                         val = loaded_settings["keybindings"][k_key]
                                         self.settings["keybindings"][k_key] = [str(v) for v in val] if isinstance(val, list) else [str(val)]
                             elif key != "keybindings":
                                 # General handling for other keys
                                 self.settings[key] = loaded_settings[key]
                    # --- END MODIFIED ---
            else:
                logger.info("No settings file found, creating with defaults.")
                self.settings = self._load_defaults()
                self.save_settings()
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading settings from {self.settings_file}: {e}. Using defaults.", exc_info=True)
            self.settings = self._load_defaults()

    def save_settings(self):
        """Saves current settings to the JSON file."""
        try:
            # --- MODIFIED: Save all current settings ---
            settings_to_save = self.settings.copy()
            # --- END MODIFIED ---
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=4)
            logger.info("Settings saved.")
        except IOError as e:
            logger.error(f"Error saving settings to {self.settings_file}: {e}", exc_info=True)

    def get_setting(self, key, default=None):
        """Gets a specific setting value."""
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        """Sets a specific setting value and saves immediately."""
        # --- MODIFIED: Allow setting known keys ---
        if key in self._load_defaults().keys():
        # --- END MODIFIED ---
            self.settings[key] = value
            self.save_settings()
        else:
            logger.warning(f"Attempted to set unknown setting key '{key}'")

    def get_current_playlist(self):
        """Gets the path to the last used playlist."""
        path = self.get_setting("current_playlist_path")
        return path if path and os.path.exists(path) else None

    def set_current_playlist(self, path):
        """Sets the path for the last used playlist."""
        self.set_setting("current_playlist_path", path)