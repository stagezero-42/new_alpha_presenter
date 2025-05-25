# myapp/gui/control_window.py
import os
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QFileDialog, QListWidget, QListWidgetItem, QHBoxLayout, QApplication # Import QApplication
)
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon

from .playlist_editor import PlaylistEditorWindow
from ..playlist.playlist import Playlist
from ..utils.paths import get_icon_file_path, get_media_path, get_playlists_path
from ..settings.settings_manager import SettingsManager
from myapp.settings.key_bindings import setup_keybindings


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        self.setWindowTitle("Control Window")
        self.display_window = display_window
        if not display_window: raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager()  # This is still needed here
        self.playlist = Playlist()
        self.current_index = -1
        self.is_displaying = False
        self.editor_window = None

        self.setup_ui()
        setup_keybindings(self, self.settings_manager)  # setup_keybindings still uses it
        self.clear_display_screen()
        self.load_last_playlist()

    # ... (setup_ui, load_last_playlist, toggle_display_window_visibility methods as before) ...
    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        playlist_buttons_layout = QHBoxLayout()
        self.load_button = QPushButton(" Load")
        self.edit_button = QPushButton(" Edit")
        self.toggle_display_button = QPushButton("Show Display")
        self.close_button = QPushButton(" Close")

        self.load_button.setIcon(QIcon(get_icon_file_path("load.png")))
        self.load_button.setToolTip("Load a playlist (Ctrl+L)")
        self.edit_button.setIcon(QIcon(get_icon_file_path("edit.png")))
        self.edit_button.setToolTip("Open the Playlist Editor (Ctrl+E)")
        self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png")))
        self.toggle_display_button.setToolTip("Show or Hide the Display Window")
        self.close_button.setIcon(QIcon(get_icon_file_path("close.png")))
        self.close_button.setToolTip("Close the application (Ctrl+Q)")

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
        self.display_button = QPushButton(" Go")
        self.prev_button = QPushButton(" Prev")
        self.next_button = QPushButton(" Next")
        self.clear_button = QPushButton(" Clear")

        self.display_button.setIcon(QIcon(get_icon_file_path("play.png")))
        self.display_button.setToolTip("Display media or clear display (Space)")
        self.prev_button.setIcon(QIcon(get_icon_file_path("previous.png")))
        self.prev_button.setToolTip("Previous slide (Arrow Keys, Page Up/Down)")
        self.next_button.setIcon(QIcon(get_icon_file_path("next.png")))
        self.next_button.setToolTip("Next slide (Arrow Keys, Page Up/Down)")
        self.clear_button.setIcon(QIcon(get_icon_file_path("clear.png")))
        self.clear_button.setToolTip("Clear display (Esc)")

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
        if self.display_window:
            if self.display_window.isVisible():
                self.display_window.hide()
                self.toggle_display_button.setText("Show Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png")))
            else:
                self.display_window.showFullScreen()
                self.toggle_display_button.setText("Hide Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("hide_display.png")))

    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(
                display_window_instance=self.display_window,
                playlist_obj=self.playlist,
                # settings_manager=self.settings_manager, # Removed
                parent=self
            )
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    # ... (rest of ControlWindow methods as before, ensure close_application, closeEvent, load_last_playlist etc. are there) ...
    def load_last_playlist(self):
        last_playlist = self.settings_manager.get_current_playlist()
        if last_playlist:
            print(f"Loading last used playlist: {last_playlist}")
            self.load_playlist(last_playlist)
        else:
            print("No last playlist found in settings.")

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        print(f"ControlWindow received signal to reload: {saved_playlist_path}")
        self.load_playlist(saved_playlist_path)

    def populate_playlist_view(self):
        self.playlist_view.clear()
        for i, slide_data in enumerate(self.playlist.get_slides()):
            layers_str = ", ".join(slide_data.get("layers", []))
            item_text = f"Slide {i + 1}: {layers_str if layers_str else '[Empty Slide]'}"
            item = QListWidgetItem(item_text)
            self.playlist_view.addItem(item)
        self.update_list_selection()

    def load_playlist_dialog(self):
        default_dir = get_playlists_path()
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
            self.settings_manager.set_current_playlist(file_path)
            print(f"Loaded: {file_path}")
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist()
            self.current_index = -1
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.settings_manager.set_current_playlist(None)

    def start_or_go_slide(self):
        if self.is_displaying:
            self.clear_display_screen()
            return
        slides = self.playlist.get_slides()
        if not slides: return
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
            self.toggle_display_window_visibility()
        slide_data = self.playlist.get_slide(self.current_index)
        if slide_data:
            self.is_displaying = True
            image_filenames = slide_data.get("layers", [])
            self.display_window.display_images(image_filenames, get_media_path())
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

    def prev_slide(self):
        slides = self.playlist.get_slides()
        if not slides: return
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()

    def clear_display_screen(self):
        if self.display_window:
            self.display_window.clear_display()
        self.is_displaying = False

    def close_application(self):
        print("Attempting to close application...")
        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close():
                print("Editor close cancelled, aborting application close.")
                return
        if self.display_window:
            print("Closing display window...")
            self.display_window.close()
        print("Closing control window...")
        self.close()
        print("Quitting QApplication instance.")
        QCoreApplication.instance().quit()

    def closeEvent(self, event):
        print("ControlWindow closeEvent triggered.")
        if self.display_window and self.display_window.isVisible():
            self.display_window.close()
        if self.editor_window and self.editor_window.isVisible():
            self.editor_window.close()
        super().closeEvent(event)
        print("ControlWindow closeEvent finished.")