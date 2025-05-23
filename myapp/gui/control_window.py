# myapp/gui/control_window.py
import os
import json
import sys
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QFileDialog, QApplication, QListWidget, QListWidgetItem,
    QHBoxLayout, QSizePolicy
)
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtCore import Qt, QCoreApplication

from .playlist_editor import PlaylistEditorWindow
from .display_window import DisplayWindow


def get_base_path():
    """Gets the base path for the application, handling frozen executables."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        self.setWindowTitle("Control Window")
        self.display_window = display_window
        self.playlist = []
        self.current_index = -1

        self.loaded_playlist_file_path = None
        self.current_playlist_directory = os.path.join(get_base_path(), "media_files")  # Default project media_files

        # --- NEW: For consistent default load location ---
        self.user_playlists_base_dir = os.path.join(get_base_path(), "user_created_playlists")
        os.makedirs(self.user_playlists_base_dir, exist_ok=True)  # Ensure it exists

        self.is_displaying = False
        self.editor_window = None

        self.setup_ui()
        self.setup_keybindings()
        self.clear_display_screen()

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        playlist_buttons_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Playlist (Ctrl+L)")
        self.edit_button = QPushButton("Edit Playlist (Ctrl+E)")
        self.close_button = QPushButton("Close Application (Ctrl+Q)")

        self.load_button.clicked.connect(self.load_playlist_dialog)
        self.edit_button.clicked.connect(self.open_playlist_editor)
        self.close_button.clicked.connect(self.close_application)

        playlist_buttons_layout.addWidget(self.load_button)
        playlist_buttons_layout.addWidget(self.edit_button)
        playlist_buttons_layout.addWidget(self.close_button)
        main_layout.addLayout(playlist_buttons_layout)

        self.playlist_view = QListWidget()
        self.playlist_view.currentItemChanged.connect(self.handle_list_selection)
        self.playlist_view.itemDoubleClicked.connect(self.go_to_selected_slide_from_list)
        main_layout.addWidget(self.playlist_view)

        playback_buttons_layout = QHBoxLayout()
        self.display_button = QPushButton("Display/Go (Space)")
        self.prev_button = QPushButton("Previous (Left Arrow)")
        self.next_button = QPushButton("Next (Right Arrow)")
        self.clear_button = QPushButton("Clear Display (Esc)")

        self.display_button.clicked.connect(self.start_or_go_slide)
        self.prev_button.clicked.connect(self.prev_slide)
        self.next_button.clicked.connect(self.next_slide)
        self.clear_button.clicked.connect(self.clear_display_screen)

        playback_buttons_layout.addWidget(self.display_button)
        playback_buttons_layout.addWidget(self.prev_button)
        playback_buttons_layout.addWidget(self.next_button)
        playback_buttons_layout.addWidget(self.clear_button)
        main_layout.addLayout(playback_buttons_layout)

        self.setCentralWidget(central_widget)
        self.resize(450, 600)

    def setup_keybindings(self):
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self.next_slide)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.prev_slide)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.start_or_go_slide)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.clear_display_screen)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close_application)
        QShortcut(QKeySequence("Ctrl+L"), self, self.load_playlist_dialog)
        QShortcut(QKeySequence("Ctrl+E"), self, self.open_playlist_editor)

    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            current_playlist_for_editor = {"slides": self.playlist} if self.playlist else None

            # PlaylistEditorWindow expects the full file path if editing an existing playlist,
            # or None if it's for a new playlist context based on defaults.
            # The current_playlist_directory is used by the editor if playlist_file_path is None initially.

            self.editor_window = PlaylistEditorWindow(
                display_window_instance=self.display_window,
                current_playlist=current_playlist_for_editor,
                # --- MODIFIED: Pass the correct argument name and value ---
                current_playlist_file_path_from_control=self.loaded_playlist_file_path,
                parent=self
            )
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        print(f"ControlWindow received playlist_saved_signal for: {saved_playlist_path}")
        if self.loaded_playlist_file_path == saved_playlist_path or self.loaded_playlist_file_path is None:
            QMessageBox.information(self, "Playlist Updated",
                                    f"Playlist '{os.path.basename(saved_playlist_path)}' was updated by the editor. Reloading.")
            self._load_playlist_from_path(saved_playlist_path)
        else:
            reply = QMessageBox.question(self, "Playlist Saved",
                                         f"Playlist saved as '{os.path.basename(saved_playlist_path)}' by the editor.\nLoad this playlist now?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self._load_playlist_from_path(saved_playlist_path)

    def populate_playlist_view(self):
        self.playlist_view.clear()
        for i, slide_data in enumerate(self.playlist):
            layers_str = ", ".join(slide_data.get("layers", []))
            item_text = f"Slide {i + 1}: {layers_str if layers_str else '[Empty Slide]'}"
            item = QListWidgetItem(item_text)
            self.playlist_view.addItem(item)

    def load_playlist_dialog(self):
        # --- MODIFIED: Default directory logic ---
        default_dir = None
        if self.loaded_playlist_file_path and os.path.isdir(os.path.dirname(self.loaded_playlist_file_path)):
            default_dir = os.path.dirname(self.loaded_playlist_file_path)
        elif os.path.isdir(self.user_playlists_base_dir):  # Prioritize user_created_playlists
            default_dir = self.user_playlists_base_dir
        elif os.path.isdir(
                self.current_playlist_directory):  # Fallback to current_playlist_directory (often media_files)
            default_dir = self.current_playlist_directory
        else:  # Final fallback
            default_dir = get_base_path()
        # --- END MODIFIED ---

        fileName, _ = QFileDialog.getOpenFileName(self, "Open Playlist", default_dir, "JSON Files (*.json)")
        if fileName:
            self._load_playlist_from_path(fileName)
            return True
        return False

    def _load_playlist_from_path(self, playlist_path_on_disk):
        print(f"ControlWindow attempting to load playlist from: {playlist_path_on_disk}")
        if not os.path.exists(playlist_path_on_disk):
            QMessageBox.warning(self, "Error", f"Playlist file not found: {playlist_path_on_disk}")
            self.playlist = []
            self.current_index = -1
            self.is_displaying = False
            self.loaded_playlist_file_path = None
            self.current_playlist_directory = os.path.join(get_base_path(), "media_files")
            self.populate_playlist_view()
            self.clear_display_screen()
            return

        try:
            with open(playlist_path_on_disk, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.playlist = data.get("slides", [])

            if not self.playlist:
                QMessageBox.information(self, "Playlist Empty", "The loaded playlist contains no slides.")
                self.current_index = -1
            else:
                self.current_index = 0

            self.loaded_playlist_file_path = playlist_path_on_disk
            self.current_playlist_directory = os.path.dirname(playlist_path_on_disk)

            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.update_list_selection()
            print(f"Playlist loaded from {playlist_path_on_disk}. {len(self.playlist)} slides.")
            print(f"ControlWindow current_playlist_directory set to: {self.current_playlist_directory}")

        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.critical(self, "Error", f"Failed to load or parse playlist: {playlist_path_on_disk}\n{e}")
            self.playlist = []
            self.current_index = -1
            self.is_displaying = False
            self.loaded_playlist_file_path = None
            self.current_playlist_directory = os.path.join(get_base_path(), "media_files")
            self.populate_playlist_view()
            self.clear_display_screen()

    def start_or_go_slide(self):
        if not self.playlist:
            print("No playlist loaded. Opening load dialog.")
            if not self.load_playlist_dialog():
                return
            if not self.playlist:
                QMessageBox.information(self, "No Playlist", "No playlist is loaded to display.")
                return

        selected_row = self.playlist_view.currentRow()
        if 0 <= selected_row < len(self.playlist):
            self.current_index = selected_row
        elif not (0 <= self.current_index < len(self.playlist)) and self.playlist:
            self.current_index = 0

        self.update_display()

    def go_to_selected_slide_from_list(self, item):
        row = self.playlist_view.row(item)
        if 0 <= row < len(self.playlist):
            self.current_index = row
            self.update_display()

    def handle_list_selection(self, current_qlistwidget_item, previous_qlistwidget_item):
        if current_qlistwidget_item:
            row = self.playlist_view.row(current_qlistwidget_item)
            if 0 <= row < len(self.playlist):
                self.current_index = row
                print(f"Selected slide index {self.current_index} (Slide {self.current_index + 1}) in list.")

    def update_display(self):
        if self.playlist and 0 <= self.current_index < len(self.playlist):
            self.is_displaying = True
            slide_data = self.playlist[self.current_index]
            image_relative_paths = slide_data.get("layers", [])

            actual_media_base = os.path.join(self.current_playlist_directory, "media_files")

            if not os.path.isdir(actual_media_base):
                print(
                    f"Warning: Media sub-directory '{actual_media_base}' not found. Trying playlist directory '{self.current_playlist_directory}' directly for media.")
                actual_media_base = self.current_playlist_directory

            if self.display_window:
                self.display_window.display_images(image_relative_paths, actual_media_base)
            self.update_list_selection()
        else:
            print(f"Cannot update display. Index {self.current_index} out of range or no playlist. Clearing display.")
            self.clear_display_screen()

    def update_list_selection(self):
        if 0 <= self.current_index < self.playlist_view.count():
            self.playlist_view.setCurrentRow(self.current_index)

    def next_slide(self):
        if not self.playlist: return
        if self.current_index < len(self.playlist) - 1:
            self.current_index += 1
            self.update_display()
        elif self.is_displaying:
            print("End of playlist reached.")

    def prev_slide(self):
        if not self.playlist: return
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()
        elif self.is_displaying:
            print("Beginning of playlist reached.")

    def clear_display_screen(self):
        if self.display_window:
            self.display_window.clear_display()
        self.is_displaying = False
        print("Display cleared by ControlWindow.")

    def close_application(self):
        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close():
                return
        QCoreApplication.instance().quit()

    def closeEvent(self, event):
        print("ControlWindow closeEvent triggered.")
        if self.display_window:
            print("Closing display window...")
            self.display_window.close()
        super().closeEvent(event)
