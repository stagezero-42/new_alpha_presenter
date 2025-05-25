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
        """Returns the default settings dictionary with fixed keybindings."""
        return {
            "current_playlist_path": None,
            "keybindings": {
                "next": ["Right", "Down", "PgDown"],  # Updated
                "prev": ["Left", "Up", "PgUp"],  # Updated
                "go": ["Space"],
                "clear": ["Escape"],
                "quit": ["Ctrl+Q"],
                "load": ["Ctrl+L"],
                "edit": ["Ctrl+E"]
            }
            # "custom_key_map" is removed
        }

    def load_settings(self):
        """Loads settings from the JSON file, merging with defaults."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)

                defaults = self._load_defaults()
                self.settings = defaults  # Start with current defaults

                # Update with loaded settings, but ensure structure for keybindings
                if "current_playlist_path" in loaded_settings:
                    self.settings["current_playlist_path"] = loaded_settings["current_playlist_path"]

                if "keybindings" in loaded_settings and isinstance(loaded_settings["keybindings"], dict):
                    # Only update keys present in defaults to avoid keeping old, unused bindings
                    for key in self.settings["keybindings"].keys():
                        if key in loaded_settings["keybindings"]:
                            val = loaded_settings["keybindings"][key]
                            # Ensure it's a list
                            self.settings["keybindings"][key] = [str(v) for v in val] if isinstance(val, list) else [
                                str(val)]
                # "custom_key_map" is no longer loaded or processed
            else:  # If no file, save current defaults
                self.settings = self._load_defaults()
                self.save_settings()
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading settings from {self.settings_file}: {e}. Using defaults.")
            self.settings = self._load_defaults()

    def save_settings(self):
        """Saves current settings to the JSON file."""
        try:
            # Only save relevant parts
            settings_to_save = {
                "current_playlist_path": self.settings.get("current_playlist_path"),
                "keybindings": self.settings.get("keybindings")
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=4)
        except IOError as e:
            print(f"Error saving settings to {self.settings_file}: {e}")

    def get_setting(self, key, default=None):
        """Gets a specific setting value."""
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        """Sets a specific setting value and saves immediately."""
        # Only allow known top-level keys to be set to prevent arbitrary additions
        if key in self._load_defaults():
            self.settings[key] = value
            self.save_settings()
        else:
            print(f"Warning: Attempted to set unknown setting key '{key}'")

    def get_current_playlist(self):
        """Gets the path to the last used playlist."""
        path = self.get_setting("current_playlist_path")
        return path if path and os.path.exists(path) else None

    def set_current_playlist(self, path):
        """Sets the path for the last used playlist."""
        self.set_setting("current_playlist_path", path)

    # Removed add_custom_key and get_custom_key_data