# myapp/gui/playlist_editor.py
import os
import json
import shutil
import sys  # For get_base_path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QFileDialog, QMessageBox,
    QListWidgetItem, QAbstractItemView, QLabel, QInputDialog
)
from PySide6.QtCore import Qt, Signal

from .layer_editor_dialog import LayerEditorDialog


def get_base_path():
    """Gets the base path for the application, handling frozen executables."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class PlaylistEditorWindow(QMainWindow):
    playlist_saved_signal = Signal(str)

    def __init__(self, display_window_instance, current_playlist=None, current_playlist_file_path_from_control=None,
                 parent=None):
        super().__init__(parent)
        self.base_title = "Playlist Editor"
        self.setWindowTitle(f"{self.base_title} [*]")
        self.setGeometry(100, 100, 700, 600)

        self.display_window = display_window_instance
        self.playlist_data = {"slides": []}
        self.playlist_file_path = None  # Full path to the .json file currently being edited/saved

        # self.media_dir is ALWAYS <directory_of_self.playlist_file_path>/media_files
        # It's where media for the *current* playlist (defined by self.playlist_file_path) should be.
        self.media_dir = None

        # self.source_media_dir_for_current_data tracks where the files for the *current in-memory playlist_data*
        # are actually located. This is important for Save As, to know where to copy from.
        self.source_media_dir_for_current_data = None

        self.user_playlists_base_dir = os.path.join(get_base_path(), "user_created_playlists")
        os.makedirs(self.user_playlists_base_dir, exist_ok=True)

        if current_playlist_file_path_from_control and os.path.exists(current_playlist_file_path_from_control):
            # Editing an existing playlist passed from ControlWindow
            self._load_playlist_file(
                current_playlist_file_path_from_control)  # This sets self.playlist_file_path, self.media_dir, and self.playlist_data
        elif current_playlist and "slides" in current_playlist:  # Fallback if only data is passed
            self.playlist_data = current_playlist
            # Cannot reliably determine playlist_file_path or media_dir without full path
            self.setWindowTitle(f"{self.base_title} - Editing (Unsaved Path) [*]")

        self.setWindowModified(False)
        self.setup_ui()
        self.populate_list()

        if not self.playlist_file_path:  # If it's a new or untitled playlist
            self.setWindowTitle(f"{self.base_title} - Untitled [*]")
            self.mark_dirty(False)

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        toolbar_layout = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.load_button = QPushButton("Load")
        self.save_button = QPushButton("Save")
        self.save_as_button = QPushButton("Save As...")
        self.done_button = QPushButton("Done")

        self.new_button.clicked.connect(self.new_playlist)
        self.load_button.clicked.connect(self.load_playlist_from_standard_location)
        self.save_button.clicked.connect(self.save_playlist)
        self.save_as_button.clicked.connect(self.save_playlist_as_new_in_standard_location)
        self.done_button.clicked.connect(self.close)

        toolbar_layout.addWidget(self.new_button)
        toolbar_layout.addWidget(self.load_button)
        toolbar_layout.addWidget(self.save_button)
        toolbar_layout.addWidget(self.save_as_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.done_button)
        main_layout.addLayout(toolbar_layout)

        self.playlist_list = QListWidget()
        self.playlist_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.playlist_list.itemDoubleClicked.connect(self.edit_slide_layers_dialog)
        main_layout.addWidget(self.playlist_list)

        slide_controls_layout = QHBoxLayout()
        self.add_slide_button = QPushButton("Add Slide")
        self.edit_layers_button = QPushButton("Edit Selected Slide Layers")
        self.preview_slide_button = QPushButton("Preview Selected Slide")
        self.remove_slide_button = QPushButton("Remove Selected Slide")

        self.add_slide_button.clicked.connect(self.add_slide)
        self.edit_layers_button.clicked.connect(self.edit_selected_slide_layers)
        self.preview_slide_button.clicked.connect(self.preview_selected_slide)
        self.remove_slide_button.clicked.connect(self.remove_slide)

        slide_controls_layout.addWidget(self.add_slide_button)
        slide_controls_layout.addWidget(self.edit_layers_button)
        slide_controls_layout.addWidget(self.preview_slide_button)
        slide_controls_layout.addWidget(self.remove_slide_button)
        main_layout.addLayout(slide_controls_layout)

        self.setCentralWidget(central_widget)

    def mark_dirty(self, dirty=True):
        self.setWindowModified(dirty)

    def populate_list(self):
        self.playlist_list.clear()
        for i, slide in enumerate(self.playlist_data.get("slides", [])):
            layers_str = ", ".join(slide.get("layers", []))
            item_text = f"Slide {i + 1}: {layers_str if layers_str else '[Empty Slide]'}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, slide)
            self.playlist_list.addItem(item)

    def new_playlist(self):
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_playlist(): return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.playlist_data = {"slides": []}
        self.playlist_file_path = None
        self.media_dir = None
        self.source_media_dir_for_current_data = None
        self.populate_list()
        self.setWindowTitle(f"{self.base_title} - Untitled [*]")
        self.mark_dirty(False)

    def add_slide(self):
        new_slide = {"layers": []}
        self.update_playlist_from_list_widget_order()
        self.playlist_data["slides"].append(new_slide)
        self.populate_list()
        self.playlist_list.setCurrentRow(self.playlist_list.count() - 1)
        self.mark_dirty()
        self.edit_selected_slide_layers()

    def remove_slide(self):
        current_item = self.playlist_list.currentItem()
        if not current_item: return
        row = self.playlist_list.row(current_item)
        del self.playlist_data["slides"][row]
        self.populate_list()
        self.mark_dirty()

    def edit_selected_slide_layers(self):
        current_item = self.playlist_list.currentItem()
        if not current_item: return
        self.edit_slide_layers_dialog(current_item)

    def edit_slide_layers_dialog(self, item):
        row = self.playlist_list.row(item)
        slide_data = self.playlist_data["slides"][row]
        current_layers = slide_data.get("layers", [])

        # media_dir for LayerEditorDialog should be where files for *this specific playlist* will reside.
        # If playlist_file_path is set, media_dir is derived from it.
        # If it's an untitled playlist, save_playlist_as will set playlist_file_path and media_dir.
        current_op_media_dir = self.media_dir
        if not current_op_media_dir:
            QMessageBox.warning(self, "Set Playlist Location",
                                "Please save this new playlist first (using 'Save As...') to establish its media location.")
            if not self.save_playlist_as_new_in_standard_location():
                return
            current_op_media_dir = self.media_dir  # media_dir is now set by save_playlist_as

        if not current_op_media_dir:  # Still no media_dir (user cancelled save)
            QMessageBox.critical(self, "Error",
                                 "Cannot edit layers without a media directory. Please save the playlist.")
            return

        editor = LayerEditorDialog(current_layers, current_op_media_dir, self.display_window, self)
        if editor.exec():
            updated_layers = editor.get_updated_layers()
            if slide_data.get("layers", []) != updated_layers:
                slide_data["layers"] = updated_layers
                self.mark_dirty()
            self.populate_list()
            self.playlist_list.setCurrentRow(row)

    def preview_selected_slide(self):
        current_item = self.playlist_list.currentItem()
        if not current_item: return
        if not self.display_window: return

        preview_media_dir = self.media_dir
        if not preview_media_dir:  # If playlist not saved yet, media_dir might be None
            # Try to use source_media_dir_for_current_data if it exists (e.g. loaded then new)
            preview_media_dir = self.source_media_dir_for_current_data

        if not preview_media_dir:
            QMessageBox.warning(self, "Preview Error",
                                "Media directory is not established. Please save the playlist first or ensure it's loaded correctly.")
            return

        row = self.playlist_list.row(current_item)
        slide_data = self.playlist_data["slides"][row]
        layers_to_preview = slide_data.get("layers", [])
        self.display_window.display_images(layers_to_preview, preview_media_dir)  # Use the determined media_dir

    def update_playlist_from_list_widget_order(self):
        new_slides_data = []
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            slide_dict = item.data(Qt.ItemDataRole.UserRole)
            if slide_dict:
                new_slides_data.append(slide_dict)
        self.playlist_data["slides"] = new_slides_data

    def load_playlist_from_standard_location(self):
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_playlist(): return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        file_name, _ = QFileDialog.getOpenFileName(self, "Load Playlist", self.user_playlists_base_dir,
                                                   "JSON Files (*.json)")
        if file_name:
            self._load_playlist_file(file_name)

    def _load_playlist_file(self, file_path_to_load):
        try:
            with open(file_path_to_load, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            if "slides" not in loaded_data or not isinstance(loaded_data["slides"], list):
                raise ValueError("Playlist must contain a 'slides' list.")

            self.playlist_data = loaded_data
            self.playlist_file_path = file_path_to_load
            self.media_dir = os.path.join(os.path.dirname(self.playlist_file_path), "media_files")
            self.source_media_dir_for_current_data = self.media_dir  # For a loaded playlist, source is its own media_dir
            os.makedirs(self.media_dir, exist_ok=True)

            self.populate_list()
            self.setWindowTitle(f"{self.base_title} - {os.path.basename(self.playlist_file_path)} [*]")
            self.mark_dirty(False)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load or parse playlist: {e}")

    def save_playlist(self):
        self.update_playlist_from_list_widget_order()
        if not self.playlist_file_path:
            return self.save_playlist_as_new_in_standard_location()
        else:
            # When saving an existing playlist, the source of files is its current media_dir
            self.source_media_dir_for_current_data = self.media_dir
            return self._save_to_path(self.playlist_file_path)

    def save_playlist_as_new_in_standard_location(self):
        self.update_playlist_from_list_widget_order()
        current_filename_suggestion = os.path.basename(
            self.playlist_file_path) if self.playlist_file_path else "untitled.json"

        filename, ok = QInputDialog.getText(self, "Save Playlist As",
                                            "Enter filename for new playlist (in user_created_playlists):",
                                            text=current_filename_suggestion)
        if ok and filename:
            if not filename.lower().endswith('.json'):
                filename += '.json'
            full_save_path = os.path.join(self.user_playlists_base_dir, filename)

            if os.path.exists(full_save_path) and \
                    (not self.playlist_file_path or os.path.normpath(full_save_path) != os.path.normpath(
                        self.playlist_file_path)):
                reply = QMessageBox.question(self, "Confirm Save As",
                                             f"'{filename}' already exists. Overwrite?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return False

            # Before calling _save_to_path for "Save As", ensure source_media_dir is set.
            # If self.media_dir is already set (e.g., from a previously loaded playlist), use it.
            # If self.media_dir is None (it was a new, unsaved playlist), then LayerEditorDialog
            # would have prompted to save, setting self.media_dir.
            # If layers were added to a new playlist *before* first save, LayerEditorDialog
            # would need a temporary place or force save.
            # The current logic in edit_slide_layers_dialog forces save if self.media_dir is None.
            # So, self.media_dir should be the source for files copied by LayerEditorDialog.
            self.source_media_dir_for_current_data = self.media_dir

            return self._save_to_path(full_save_path)
        return False

    def _save_to_path(self, path_to_save_json):
        new_playlist_json_dir = os.path.dirname(path_to_save_json)
        new_target_media_dir = os.path.join(new_playlist_json_dir, "media_files")
        os.makedirs(new_target_media_dir, exist_ok=True)

        # Files listed in self.playlist_data.slides[*].layers are relative filenames.
        # Their actual source files are expected to be in self.source_media_dir_for_current_data.
        if not self.source_media_dir_for_current_data:
            # This can happen if it's a new playlist, layers added, but never saved before,
            # and LayerEditorDialog didn't manage to set a source_media_dir.
            # This case should ideally be handled by LayerEditorDialog forcing a save or using a temp dir.
            # For now, if source is None, we can't copy, but JSON will be saved.
            print(
                f"Warning: source_media_dir_for_current_data is not set during save. Media files might not be copied if they are not already in {new_target_media_dir}.")

        for slide in self.playlist_data.get("slides", []):
            for layer_filename in slide.get("layers", []):
                target_file_path = os.path.join(new_target_media_dir, layer_filename)

                if not os.path.exists(target_file_path) and self.source_media_dir_for_current_data:
                    potential_source_path = os.path.join(self.source_media_dir_for_current_data, layer_filename)
                    if os.path.exists(potential_source_path):
                        try:
                            # Ensure we don't copy a file onto itself if source and target media dirs are the same
                            if os.path.normpath(potential_source_path) != os.path.normpath(target_file_path):
                                shutil.copy2(potential_source_path, target_file_path)
                                print(f"Save Op: Copied '{potential_source_path}' to '{target_file_path}'")
                        except Exception as e:
                            print(f"Save Op: Error copying '{potential_source_path}' to '{target_file_path}': {e}")
                    else:
                        print(
                            f"Save Op Warning: Layer '{layer_filename}' source file not found in '{self.source_media_dir_for_current_data}'. Cannot copy to '{new_target_media_dir}'.")
                elif os.path.exists(target_file_path):
                    pass  # File already in target, no copy needed.
                # else: (no source_media_dir_for_current_data and file not in target) -> file will be missing.

        try:
            with open(path_to_save_json, 'w', encoding='utf-8') as f:
                json.dump(self.playlist_data, f, indent=4)

            self.playlist_file_path = path_to_save_json
            self.media_dir = new_target_media_dir  # Update editor's primary media_dir
            self.source_media_dir_for_current_data = self.media_dir  # After save, source is the new media_dir

            self.setWindowTitle(f"{self.base_title} - {os.path.basename(self.playlist_file_path)} [*]")
            self.mark_dirty(False)
            QMessageBox.information(self, "Save Success", f"Playlist saved to {path_to_save_json}")
            self.playlist_saved_signal.emit(path_to_save_json)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save playlist JSON: {e}")
            return False

    def prompt_save_changes(self):
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "You have unsaved changes. Do you want to save them before proceeding?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)
        return reply

    def closeEvent(self, event):
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_playlist():
                    event.ignore();
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore();
                return

        event.accept()
        if event.isAccepted():
            print("PlaylistEditorWindow closing.")
            if self.display_window:
                self.display_window.clear_display()
