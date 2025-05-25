# myapp/settings/settings_manager.py
import json
import os
from ..utils.paths import get_settings_file_path

class SettingsManager:
    def __init__(self):
        self.settings_file = get_settings_file_path()
        self.settings = self._load_defaults()
        self.load_settings()

    def _load_defaults(self):
        """Returns the default settings dictionary."""
        return {
            "current_playlist_path": None,
            "keybindings": { # Example - can be expanded
                "next": "Right",
                "prev": "Left",
                "go": "Space",
                "clear": "Escape",
                "quit": "Ctrl+Q",
                "load": "Ctrl+L",
                "edit": "Ctrl+E"
            }
        }

    def load_settings(self):
        """Loads settings from the JSON file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Merge loaded settings over defaults to handle new keys
                    self.settings.update(loaded_settings)
            else:
                # If no file, save defaults
                self.save_settings()
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading settings from {self.settings_file}: {e}. Using defaults.")
            self.settings = self._load_defaults()

    def save_settings(self):
        """Saves current settings to the JSON file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            print(f"Error saving settings to {self.settings_file}: {e}")

    def get_setting(self, key, default=None):
        """Gets a specific setting value."""
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        """Sets a specific setting value and saves immediately."""
        self.settings[key] = value
        self.save_settings()

    def get_current_playlist(self):
        """Gets the path to the last used playlist."""
        path = self.get_setting("current_playlist_path")
        # Ensure the path exists before returning it
        return path if path and os.path.exists(path) else None

    def set_current_playlist(self, path):
        """Sets the path for the last used playlist."""
        self.set_setting("current_playlist_path", path)