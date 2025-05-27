# myapp/gui/control_window.py
import os
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QFileDialog, QListWidget, QListWidgetItem, QHBoxLayout, QApplication,
    QListView, QAbstractItemView
)
from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

from .playlist_editor import PlaylistEditorWindow
from ..playlist.playlist import Playlist
# --- MODIFIED: Added get_playlist_file_path ---
from ..utils.paths import get_icon_file_path, get_media_path, get_playlists_path, get_playlist_file_path
# --- END MODIFIED ---
from ..settings.settings_manager import SettingsManager
from myapp.settings.key_bindings import setup_keybindings
from myapp import __version__
from .thumbnail_generator import (
    create_composite_thumbnail,
    get_thumbnail_size,
    get_list_widget_height
)
from .slide_timer import SlideTimer
from .widget_helpers import create_button

class ControlWindow(QMainWindow):
    # ... (__init__, _load_indicator_icons, setup_ui remain mostly the same) ...
    def __init__(self, display_window):
        super().__init__()
        self.setWindowTitle(f"Control Window v{__version__}")
        self.display_window = display_window
        if not display_window: raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager() #
        self.playlist = Playlist() #
        self.current_index = -1
        self.is_displaying = False
        self.editor_window = None
        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)
        self.indicator_icons = self._load_indicator_icons()

        self.setup_ui()
        setup_keybindings(self, self.settings_manager) #
        self.update_show_clear_button_state()
        self.clear_display_screen()
        self.load_last_playlist()

    def _load_indicator_icons(self):
        """Loads and scales indicator icons into a dictionary."""
        icons = {}
        icon_files = {
            "slide": "slide_icon.png",
            "timer": "timer_icon.png",
            "loop": "loop_icon.png"
        }
        size = 16
        for name, filename in icon_files.items():
            try:
                pixmap = QPixmap(get_icon_file_path(filename)).scaled( #
                    size, size, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                icons[name] = pixmap
            except Exception as e:
                print(f"Warning: Could not load icon '{filename}': {e}")
                icons[name] = QPixmap()
        return icons

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        playlist_buttons_layout = QHBoxLayout()
        self.load_button = create_button(
            " Load", "load.png", "Load a playlist (Ctrl+L)", self.load_playlist_dialog
        )
        self.edit_button = create_button(
            " Edit", "edit.png", "Open the Playlist Editor (Ctrl+E)", self.open_playlist_editor
        )
        self.toggle_display_button = create_button(
            "Show Display", "show_display.png", "Show or Hide the Display Window", self.toggle_display_window_visibility
        )
        self.close_button = create_button(
            " Close", "close.png", "Close the application (Ctrl+Q)", self.close_application
        )

        playlist_buttons_layout.addWidget(self.load_button)
        playlist_buttons_layout.addWidget(self.edit_button)
        playlist_buttons_layout.addWidget(self.toggle_display_button)
        playlist_buttons_layout.addWidget(self.close_button)
        main_layout.addLayout(playlist_buttons_layout)

        self.playlist_view = QListWidget()
        self.playlist_view.setViewMode(QListView.ViewMode.IconMode)
        self.playlist_view.setFlow(QListView.Flow.LeftToRight)
        self.playlist_view.setMovement(QListView.Movement.Static)
        self.playlist_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.playlist_view.setWrapping(False)
        self.playlist_view.setIconSize(get_thumbnail_size())
        self.playlist_view.setFixedHeight(get_list_widget_height())
        self.playlist_view.setSpacing(5)
        self.playlist_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlist_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.playlist_view.currentItemChanged.connect(self.handle_list_selection)
        self.playlist_view.itemDoubleClicked.connect(self.go_to_selected_slide_from_list)
        main_layout.addWidget(self.playlist_view)

        playback_buttons_layout = QHBoxLayout()
        self.show_clear_button = QPushButton()
        self.show_clear_button.clicked.connect(self.handle_show_clear_click)
        self.prev_button = create_button(
            " Prev", "previous.png", "Previous slide (Arrow Keys, Page Up/Down)", self.prev_slide
        )
        self.next_button = create_button(
            " Next", "next.png", "Next slide (Arrow Keys, Page Up/Down)", self.next_slide
        )

        playback_buttons_layout.addWidget(self.show_clear_button)
        playback_buttons_layout.addWidget(self.prev_button)
        playback_buttons_layout.addWidget(self.next_button)
        main_layout.addLayout(playback_buttons_layout)

        self.setCentralWidget(central_widget)
        self.resize(600, 350)
        self.update_show_clear_button_state()

    def populate_playlist_view(self):
        self.playlist_view.clear()
        # --- MODIFIED: Removed media_base_path, call thumbnail gen without it ---
        for i, slide_data in enumerate(self.playlist.get_slides()): #
            composite_icon = create_composite_thumbnail(
                slide_data, i, self.indicator_icons
            )
        # --- END MODIFIED ---
            item = QListWidgetItem(composite_icon, "")

            tooltip_parts = [f"Slide {i + 1}"]
            duration = slide_data.get("duration", 0)
            loop_target = slide_data.get("loop_to_slide", 0)

            if duration > 0:
                tooltip_parts.append(f"Plays for: {duration}s")
            else:
                tooltip_parts.append("Manual advance")

            if loop_target > 0:
                if duration > 0:
                    tooltip_parts.append(f"Loops to: Slide {loop_target}")
                else:
                    tooltip_parts.append(f"Loop to Slide {loop_target} (inactive due to 0s duration)")

            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_view.addItem(item)

        self.update_list_selection()

    # ... (auto_advance_or_loop_slide, update_show_clear_button_state, etc. remain the same) ...
    def auto_advance_or_loop_slide(self):
        """Handles the timer timeout to advance or loop."""
        print("Timer triggered.")
        if not self.is_displaying:
            print("Display not active, timer ignored.")
            return

        current_slide_data = self.playlist.get_slide(self.current_index) #
        if not current_slide_data:
            print("No current slide data, timer ignored.")
            return

        num_slides = len(self.playlist.get_slides()) #
        loop_target_1_based = current_slide_data.get("loop_to_slide", 0)
        duration = current_slide_data.get("duration", 0)

        # Check if loop is valid and intended
        if duration > 0 and loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1

            if loop_target_0_based == self.current_index:
                print(f"Slide {self.current_index + 1} loops to itself. Ignoring loop.")
            elif 0 <= loop_target_0_based < num_slides:
                print(f"Looping from slide {self.current_index + 1} to slide {loop_target_1_based}.")
                self.current_index = loop_target_0_based
                self.update_display() # This will restart the timer if needed
                return # Exit, as we've looped
            else:
                print(f"Invalid loop target ({loop_target_1_based}). Ignoring loop.")

        # If no loop occurred, try to advance
        if self.current_index < (num_slides - 1):
            print("Auto-advancing to next slide.")
            self.next_slide() # This will call update_display
        else:
            print("Timer expired on the last slide or no valid action, stopping.")


    def update_show_clear_button_state(self):
        if self.is_displaying:
            self.show_clear_button.setText(" Clear")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("clear.png"))) #
            self.show_clear_button.setToolTip("Clear the display (Space or Esc)")
        else:
            self.show_clear_button.setText(" Show")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("play.png"))) #
            self.show_clear_button.setToolTip("Show the selected slide (Space)")


    def handle_show_clear_click(self):
        if self.slide_timer.is_active():
            self.slide_timer.stop()
        if self.is_displaying:
            self.clear_display_screen()
        else:
            self.start_or_go_slide()

    def toggle_display_window_visibility(self):
        if self.display_window:
            if self.display_window.isVisible():
                self.display_window.hide()
                self.toggle_display_button.setText("Show Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png"))) #
            else:
                self.display_window.showFullScreen()
                self.toggle_display_button.setText("Hide Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("hide_display.png"))) #


    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(
                display_window_instance=self.display_window,
                playlist_obj=self.playlist,
                parent=self
            )
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        print(f"ControlWindow received signal to reload: {saved_playlist_path}")
        self.load_playlist(saved_playlist_path)


    def load_playlist_dialog(self):
        default_dir = get_playlists_path() #
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Playlist", default_dir, "JSON Files (*.json)")
        if fileName:
            self.load_playlist(fileName)
            return True
        return False

    def load_playlist(self, file_path):
        try:
            self.playlist.load(file_path) #
            self.current_index = 0 if self.playlist.get_slides() else -1 #
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.settings_manager.set_current_playlist(file_path) #
            print(f"Loaded: {file_path}")
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist() #
            self.current_index = -1
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.settings_manager.set_current_playlist(None) #

    def load_last_playlist(self):
        last_playlist = self.settings_manager.get_current_playlist() #
        if last_playlist:
            print(f"Loading last used playlist: {last_playlist}")
            self.load_playlist(last_playlist)
        else:
            print("No last playlist found in settings.")
            self.clear_display_screen()


    def start_or_go_slide(self):
        self.slide_timer.stop()
        slides = self.playlist.get_slides() #
        if not slides:
            QMessageBox.information(self, "No Playlist", "Load a playlist to show a slide.")
            return
        current_item = self.playlist_view.currentItem()
        if current_item:
            self.current_index = current_item.data(Qt.ItemDataRole.UserRole)
        elif not (0 <= self.current_index < len(slides)):
            self.current_index = 0

        self.update_display()


    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        self.slide_timer.stop()
        if item:
            self.current_index = item.data(Qt.ItemDataRole.UserRole)
            self.update_display()


    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        if current_item:
            new_index = current_item.data(Qt.ItemDataRole.UserRole)
            if self.slide_timer.is_active() and new_index != self.current_index:
                self.slide_timer.stop()
            self.current_index = new_index


    def update_display(self):
        self.slide_timer.stop()

        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index) #

        if slide_data:
            self.is_displaying = True
            image_filenames = slide_data.get("layers", [])
            # --- MODIFIED: Call without media_base_path ---
            self.display_window.display_images(image_filenames) #
            # --- END MODIFIED ---
            self.update_list_selection()

            duration = slide_data.get("duration", 0)
            self.slide_timer.start(duration)

        else:
            self.is_displaying = False
            if self.display_window: self.display_window.clear_display() #

        self.update_show_clear_button_state()


    def update_list_selection(self):
        if 0 <= self.current_index < self.playlist_view.count():
            for i in range(self.playlist_view.count()):
                item = self.playlist_view.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == self.current_index:
                    self.playlist_view.setCurrentItem(item)
                    self.playlist_view.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                    break


    def next_slide(self):
        self.slide_timer.stop()
        slides = self.playlist.get_slides() #
        if not slides: return
        if self.current_index < len(slides) - 1:
            self.current_index += 1
            self.update_display()
        elif self.is_displaying:
            print("End of playlist reached (from Next button).")


    def prev_slide(self):
        self.slide_timer.stop()
        slides = self.playlist.get_slides() #
        if not slides: return
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()
        elif self.is_displaying:
            print("Beginning of playlist reached (from Prev button).")


    def clear_display_screen(self):
        self.slide_timer.stop()
        if self.display_window:
            self.display_window.clear_display() #
        self.is_displaying = False
        self.update_show_clear_button_state()
        print("Display cleared by ControlWindow.")


    def close_application(self):
        print("Attempting to close application...")
        self.slide_timer.stop()
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
        self.slide_timer.stop()
        if self.display_window and self.display_window.isVisible():
            self.display_window.close()
        if self.editor_window and self.editor_window.isVisible():
            self.editor_window.close()
        super().closeEvent(event)
        print("ControlWindow closeEvent finished.")