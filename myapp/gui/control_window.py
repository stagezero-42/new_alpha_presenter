# myapp/gui/control_window.py
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QFileDialog, QListWidget, QListWidgetItem,
    QHBoxLayout
)
from PySide6.QtCore import QCoreApplication

# Local application imports
from .playlist_editor import PlaylistEditorWindow
from ..playlist.playlist import Playlist, get_base_path
from myapp.settings.key_bindings import setup_keybindings


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        self.setWindowTitle("Control Window")
        self.display_window = display_window
        if not display_window:
            raise ValueError("DisplayWindow instance must be provided.")

        self.playlist = Playlist()
        self.current_index = -1
        self.is_displaying = False
        self.editor_window = None

        self.setup_ui()
        setup_keybindings(self)
        self.clear_display_screen()

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        playlist_buttons_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Playlist (Ctrl+L)")
        self.edit_button = QPushButton("Edit Playlist (Ctrl+E)")
        # --- CHANGE: Default text is now "Show Display" ---
        self.toggle_display_button = QPushButton("Show Display")
        # --- END CHANGE ---
        self.close_button = QPushButton("Close Application (Ctrl+Q)")

        self.load_button.clicked.connect(self.load_playlist_dialog)
        self.edit_button.clicked.connect(self.open_playlist_editor)
        self.toggle_display_button.clicked.connect(self.toggle_display_window_visibility)
        self.close_button.clicked.connect(self.close_application)

        playlist_buttons_layout.addWidget(self.load_button)
        playlist_buttons_layout.addWidget(self.edit_button)
        playlist_buttons_layout.addWidget(self.toggle_display_button)
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

    def toggle_display_window_visibility(self):
        """Shows or hides the entire display window."""
        if self.display_window:
            if self.display_window.isVisible():
                self.display_window.hide()
                self.toggle_display_button.setText("Show Display")
            else:
                self.display_window.showFullScreen()
                self.toggle_display_button.setText("Hide Display")

    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(
                display_window_instance=self.display_window,
                playlist=self.playlist,
                parent=self
            )
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        current_path = self.playlist.file_path
        if current_path == saved_playlist_path or current_path is None:
            QMessageBox.information(self, "Playlist Updated",
                                    f"Playlist '{os.path.basename(saved_playlist_path)}' was updated. Reloading.")
            self.load_playlist(saved_playlist_path)
        else:
            reply = QMessageBox.question(self, "Playlist Saved",
                                         f"Playlist saved as '{os.path.basename(saved_playlist_path)}'.\nLoad this playlist now?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.load_playlist(saved_playlist_path)

    def populate_playlist_view(self):
        self.playlist_view.clear()
        for i, slide_data in enumerate(self.playlist.get_slides()):
            layers_str = ", ".join(slide_data.get("layers", []))
            item_text = f"Slide {i + 1}: {layers_str if layers_str else '[Empty Slide]'}"
            item = QListWidgetItem(item_text)
            self.playlist_view.addItem(item)

    def load_playlist_dialog(self):
        default_dir = self.playlist.get_user_playlists_base_dir()
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Playlist", default_dir, "JSON Files (*.json)")
        if fileName:
            self.load_playlist(fileName)
            return True
        return False

    def load_playlist(self, file_path):
        try:
            self.playlist.load(file_path)
            self.current_index = 0 if self.playlist.get_slides() else -1
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.update_list_selection()
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist() # Reset to an empty playlist
            self.current_index = -1
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()

    def start_or_go_slide(self):
        """
        Toggles the display. If off, it displays the selected or first slide.
        If on, it clears the display.
        """
        if self.is_displaying:
            self.clear_display_screen()
            return

        slides = self.playlist.get_slides()
        if not slides:
            if not self.load_playlist_dialog(): return
            slides = self.playlist.get_slides()
            if not slides:
                QMessageBox.information(self, "No Playlist", "No playlist is loaded to display.")
                return

        selected_row = self.playlist_view.currentRow()

        if 0 <= selected_row < len(slides):
            self.current_index = selected_row
        elif not (0 <= self.current_index < len(slides)):
            self.current_index = 0

        self.update_display()

    def go_to_selected_slide_from_list(self, item):
        row = self.playlist_view.row(item)
        if 0 <= row < len(self.playlist.get_slides()):
            self.current_index = row
            self.update_display()

    def handle_list_selection(self, current_qlistwidget_item, previous_qlistwidget_item):
        if current_qlistwidget_item:
            row = self.playlist_view.row(current_qlistwidget_item)
            if 0 <= row < len(self.playlist.get_slides()):
                self.current_index = row

    def update_display(self):
        if self.display_window and not self.display_window.isVisible():
            self.display_window.showFullScreen()
            self.toggle_display_button.setText("Hide Display")

        slide_data = self.playlist.get_slide(self.current_index)
        media_dir = self.playlist.get_media_dir()

        if slide_data and media_dir:
            self.is_displaying = True
            image_relative_paths = slide_data.get("layers", [])
            self.display_window.display_images(image_relative_paths, media_dir)
            self.update_list_selection()
        else:
            self.clear_display_screen()

    def update_list_selection(self):
        if 0 <= self.current_index < self.playlist_view.count():
            self.playlist_view.setCurrentRow(self.current_index)

    def next_slide(self):
        slides = self.playlist.get_slides()
        if not slides: return
        if self.current_index < len(slides) - 1:
            self.current_index += 1
            self.update_display()
        elif self.is_displaying:
            print("End of playlist reached.")

    def prev_slide(self):
        slides = self.playlist.get_slides()
        if not slides: return
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
        if self.display_window:
            self.display_window.close()
        super().closeEvent(event)