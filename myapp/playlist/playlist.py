# myapp/playlist/playlist.py
import os
import json
import shutil
import sys

def get_base_path():
    """Gets the base path for the application, handling frozen executables."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

class Playlist:
    def __init__(self, file_path=None):
        self.file_path = file_path
        self.slides = []
        self.media_dir = None
        self.user_playlists_base_dir = os.path.join(get_base_path(), "user_created_playlists")
        os.makedirs(self.user_playlists_base_dir, exist_ok=True)

        if file_path:
            self.load(file_path)

    def load(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Playlist file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.slides = data.get("slides", [])
            self.file_path = file_path
            self.media_dir = os.path.join(os.path.dirname(self.file_path), "media_files")
            os.makedirs(self.media_dir, exist_ok=True)

        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to load or parse playlist: {file_path}\n{e}")

    def save(self, file_path=None):
        if file_path:
            self.file_path = file_path

        if not self.file_path:
            raise ValueError("Playlist file path not set.")

        new_playlist_json_dir = os.path.dirname(self.file_path)
        new_target_media_dir = os.path.join(new_playlist_json_dir, "media_files")
        os.makedirs(new_target_media_dir, exist_ok=True)

        for slide in self.slides:
            for layer_filename in slide.get("layers", []):
                target_file_path = os.path.join(new_target_media_dir, layer_filename)

                if not os.path.exists(target_file_path) and self.media_dir:
                    potential_source_path = os.path.join(self.media_dir, layer_filename)
                    if os.path.exists(potential_source_path):
                        try:
                            if os.path.normpath(potential_source_path) != os.path.normpath(target_file_path):
                                shutil.copy2(potential_source_path, target_file_path)
                        except Exception as e:
                            print(f"Save Op: Error copying '{potential_source_path}' to '{target_file_path}': {e}")

        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump({"slides": self.slides}, f, indent=4)

        self.media_dir = new_target_media_dir

    def add_slide(self, slide_data):
        self.slides.append(slide_data)

    def remove_slide(self, index):
        if 0 <= index < len(self.slides):
            del self.slides[index]

    def update_slide(self, index, slide_data):
        if 0 <= index < len(self.slides):
            self.slides[index] = slide_data

    def get_slide(self, index):
        if 0 <= index < len(self.slides):
            return self.slides[index]
        return None

    def get_slides(self):
        return self.slides

    def get_media_dir(self):
        return self.media_dir

    def set_media_dir(self, media_dir):
        self.media_dir = media_dir

    def get_user_playlists_base_dir(self):
        return self.user_playlists_base_dir

    def copy_media_file(self, source_file_path):
        if not self.media_dir:
            raise ValueError("Media directory not set.")

        dest_file_name = os.path.basename(source_file_path)
        dest_path = os.path.join(self.media_dir, dest_file_name)

        if not os.path.exists(dest_path) or not os.path.samefile(source_file_path, dest_path):
            shutil.copy2(source_file_path, dest_path)

        return dest_file_name