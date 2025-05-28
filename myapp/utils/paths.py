# myapp/utils/paths.py
import os
import sys

def get_project_root():
    """Gets the base path for the application project root."""
    if getattr(sys, 'frozen', False):
        # If running as a bundled executable (e.g., PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # If running as a script, go up two levels from myapp/utils/
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def get_assets_path():
    """Returns the path to the main 'assets' directory."""
    return os.path.join(get_project_root(), "assets")

def get_icons_path():
    """Returns the path to the 'icons' directory."""
    return os.path.join(get_assets_path(), "icons")

def get_icon_file_path(icon_name):
    """Returns the full path for a specific icon."""
    return os.path.join(get_icons_path(), icon_name)

def get_playlists_path():
    """Returns the path to the 'playlists' directory."""
    return os.path.join(get_assets_path(), "playlists")

def get_playlist_file_path(playlist_name):
    """Returns the full path for a specific playlist file."""
    return os.path.join(get_playlists_path(), playlist_name)

def get_media_path():
    """Returns the path to the 'media' directory."""
    return os.path.join(get_assets_path(), "media")

def get_media_file_path(media_name):
    """Returns the full path for a specific media file."""
    return os.path.join(get_media_path(), media_name)

# --- NEW FUNCTION ---
def get_texts_path():
    """Returns the path to the 'texts' directory."""
    return os.path.join(get_assets_path(), "texts")
# --- END NEW FUNCTION ---

# --- NEW FUNCTION ---
def get_text_file_path(paragraph_name):
    """Returns the full path for a specific paragraph .json file."""
    return os.path.join(get_texts_path(), f"{paragraph_name}.json")
# --- END NEW FUNCTION ---

def get_settings_file_path():
    """Returns the path to the 'settings.json' file."""
    return os.path.join(get_assets_path(), "settings.json")

def ensure_assets_folders_exist():
    """Creates all necessary assets subfolders if they don't exist."""
    os.makedirs(get_assets_path(), exist_ok=True)
    os.makedirs(get_icons_path(), exist_ok=True)
    os.makedirs(get_playlists_path(), exist_ok=True)
    os.makedirs(get_media_path(), exist_ok=True)
    os.makedirs(get_texts_path(), exist_ok=True) # --- ADDED ---