# myapp/gui/control_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QListWidget, QListWidgetItem, QHBoxLayout, QApplication, # Removed QFileDialog
    QListView, QAbstractItemView
)
from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

# --- MODIFIED: Import new helper ---
from .file_dialog_helpers import get_themed_open_filename
# --- END MODIFIED ---
from .playlist_editor import PlaylistEditorWindow
from ..playlist.playlist import Playlist
from ..utils.paths import get_icon_file_path, get_media_path, get_playlists_path
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

logger = logging.getLogger(__name__)

class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        logger.debug("Initializing ControlWindow...")
        self.setWindowTitle(f"Control Window v{__version__}")

        # --- ADD THIS CODE ---
        try:
            icon_name = "app_icon.png"  # Your icon filename
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logger.debug(f"Set window icon from: {icon_path}")
            else:
                logger.warning(f"Window icon '{icon_name}' not found at expected path: {icon_path}")
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}", exc_info=True)
        # --- END OF ADDED CODE ---

        self.display_window = display_window
        if not display_window:
            logger.critical("DisplayWindow instance must be provided.")
            raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager()
        self.playlist = Playlist()
        self.current_index = -1
        self.is_displaying = False
        self.editor_window = None

        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)

        self.indicator_icons = self._load_indicator_icons()

        self.setup_ui()
        setup_keybindings(self, self.settings_manager)
        self.update_show_clear_button_state()
        self.clear_display_screen()
        self.load_last_playlist()
        logger.debug("ControlWindow initialization complete.")

    def _load_indicator_icons(self):
        """Loads and scales indicator icons into a dictionary."""
        logger.debug("Loading indicator icons...")
        icons = {}
        icon_files = {
            "slide": "slide_icon.png",
            "timer": "timer_icon.png",
            "loop": "loop_icon.png"
        }
        size = 16
        for name, filename in icon_files.items():
            try:
                pixmap = QPixmap(get_icon_file_path(filename)).scaled(
                    size, size, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                icons[name] = pixmap
            except Exception as e:
                logger.warning(f"Could not load indicator icon '{filename}': {e}")
                icons[name] = QPixmap()
        logger.debug("Indicator icons loaded.")
        return icons

    def setup_ui(self):
        logger.debug("Setting up ControlWindow UI...")
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
        logger.debug("ControlWindow UI setup complete.")

    def populate_playlist_view(self):
        logger.debug("Populating playlist view...")
        self.playlist_view.clear()

        for i, slide_data in enumerate(self.playlist.get_slides()):
            composite_icon = create_composite_thumbnail(
                slide_data, i, self.indicator_icons
            )
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
        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")

    def auto_advance_or_loop_slide(self):
        logger.debug("Timer triggered for auto-advance/loop.")
        if not self.is_displaying:
            logger.debug("Display not active, timer ignored.")
            return

        current_slide_data = self.playlist.get_slide(self.current_index)
        if not current_slide_data:
            logger.warning("No current slide data found, timer ignored.")
            return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = current_slide_data.get("loop_to_slide", 0)
        duration = current_slide_data.get("duration", 0)

        if duration > 0 and loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1

            if loop_target_0_based == self.current_index:
                logger.debug(f"Slide {self.current_index + 1} loops to itself. Ignoring loop, proceeding.")
            elif 0 <= loop_target_0_based < num_slides:
                logger.info(f"Looping from slide {self.current_index + 1} to slide {loop_target_1_based}.")
                self.current_index = loop_target_0_based
                self.update_display()
                return
            else:
                logger.warning(f"Invalid loop target ({loop_target_1_based}) from slide {self.current_index + 1}. Ignoring loop.")

        if self.current_index < (num_slides - 1):
            logger.info("Auto-advancing to next slide.")
            self.next_slide()
        else:
            logger.info("Timer expired on the last slide or no valid action, stopping.")

    def update_show_clear_button_state(self):
        logger.debug(f"Updating show/clear button state. Is displaying: {self.is_displaying}")
        if self.is_displaying:
            self.show_clear_button.setText(" Clear")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("clear.png")))
            self.show_clear_button.setToolTip("Clear the display (Space or Esc)")
        else:
            self.show_clear_button.setText(" Show")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.show_clear_button.setToolTip("Show the selected slide (Space)")

    def handle_show_clear_click(self):
        logger.debug("Show/Clear button clicked.")
        if self.slide_timer.is_active():
            self.slide_timer.stop()
            logger.debug("Timer stopped by manual Show/Clear click.")
        if self.is_displaying:
            self.clear_display_screen()
        else:
            self.start_or_go_slide()

    def toggle_display_window_visibility(self):
        if self.display_window:
            if self.display_window.isVisible():
                logger.info("Hiding display window.")
                self.display_window.hide()
                self.toggle_display_button.setText("Show Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png")))
            else:
                logger.info("Showing display window (fullscreen).")
                self.display_window.showFullScreen()
                self.toggle_display_button.setText("Hide Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("hide_display.png")))

    def open_playlist_editor(self):
        logger.info("Opening playlist editor...")
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(
                display_window_instance=self.display_window,
                playlist_obj=self.playlist,
                parent=self
            )
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            logger.debug("Playlist editor already open, activating.")
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        logger.info(f"ControlWindow received signal to reload: {saved_playlist_path}")
        self.load_playlist(saved_playlist_path)

    def load_playlist_dialog(self):
        logger.debug("Opening load playlist dialog...")
        default_dir = get_playlists_path()
        # --- MODIFIED: Use new helper ---
        fileName = get_themed_open_filename(self, "Open Playlist", default_dir, "JSON Files (*.json)")
        # --- END MODIFIED ---
        if fileName:
            self.load_playlist(fileName)
            return True
        else:
            logger.debug("Load playlist dialog cancelled.")
            return False

    def load_playlist(self, file_path):
        logger.info(f"Attempting to load playlist: {file_path}")
        try:
            self.playlist.load(file_path)
            self.current_index = 0 if self.playlist.get_slides() else -1
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.settings_manager.set_current_playlist(file_path)
            logger.info(f"Successfully loaded: {file_path}")
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load playlist {file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist()
            self.current_index = -1
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.settings_manager.set_current_playlist(None)

    def load_last_playlist(self):
        last_playlist = self.settings_manager.get_current_playlist()
        if last_playlist:
            logger.info(f"Loading last used playlist: {last_playlist}")
            self.load_playlist(last_playlist)
        else:
            logger.info("No last playlist found in settings.")
            self.clear_display_screen()

    def start_or_go_slide(self):
        logger.debug("Start/Go triggered.")
        self.slide_timer.stop()
        slides = self.playlist.get_slides()
        if not slides:
            logger.warning("Start/Go called but no playlist loaded.")
            QMessageBox.information(self, "No Playlist", "Load a playlist to show a slide.")
            return
        current_item = self.playlist_view.currentItem()
        if current_item:
            self.current_index = current_item.data(Qt.ItemDataRole.UserRole)
            logger.debug(f"Selected slide index from list: {self.current_index}")
        elif not (0 <= self.current_index < len(slides)):
            self.current_index = 0
            logger.debug(f"No selection, defaulting to index: {self.current_index}")

        self.update_display()

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        logger.debug("Slide list double-clicked.")
        self.slide_timer.stop()
        if item:
            self.current_index = item.data(Qt.ItemDataRole.UserRole)
            logger.info(f"Jumping to slide {self.current_index + 1} from list.")
            self.update_display()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        if current_item:
            new_index = current_item.data(Qt.ItemDataRole.UserRole)
            logger.debug(f"List selection changed to index {new_index}.")
            if self.slide_timer.is_active() and new_index != self.current_index:
                self.slide_timer.stop()
                logger.debug("Timer stopped due to new slide selection in list.")
            self.current_index = new_index

    def update_display(self):
        self.slide_timer.stop()
        logger.info(f"Updating display to slide {self.current_index + 1}.")

        if self.display_window and not self.display_window.isVisible():
            logger.info("Display window not visible, showing now.")
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index)

        if slide_data:
            self.is_displaying = True
            image_filenames = slide_data.get("layers", [])
            logger.debug(f"Displaying layers: {image_filenames}")
            self.display_window.display_images(image_filenames)
            self.update_list_selection()

            duration = slide_data.get("duration", 0)
            if duration > 0:
                logger.debug(f"Starting timer for slide {self.current_index + 1} ({duration}s).")
                self.slide_timer.start(duration)
            else:
                logger.debug(f"Slide {self.current_index + 1} has 0s duration (manual advance).")
        else:
            logger.warning(f"No slide data found for index {self.current_index}. Clearing display.")
            self.is_displaying = False
            if self.display_window: self.display_window.clear_display()

        self.update_show_clear_button_state()

    def update_list_selection(self):
        logger.debug(f"Updating list selection highlight to index {self.current_index}.")
        if 0 <= self.current_index < self.playlist_view.count():
            for i in range(self.playlist_view.count()):
                item = self.playlist_view.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == self.current_index:
                    self.playlist_view.setCurrentItem(item)
                    self.playlist_view.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                    break

    def next_slide(self):
        logger.debug("Next slide triggered.")
        self.slide_timer.stop()
        slides = self.playlist.get_slides()
        if not slides: return
        if self.current_index < len(slides) - 1:
            self.current_index += 1
            self.update_display()
        elif self.is_displaying:
            logger.info("End of playlist reached (from Next button).")

    def prev_slide(self):
        logger.debug("Previous slide triggered.")
        self.slide_timer.stop()
        slides = self.playlist.get_slides()
        if not slides: return
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()
        elif self.is_displaying:
            logger.info("Beginning of playlist reached (from Prev button).")

    def clear_display_screen(self):
        logger.info("Clearing display screen.")
        self.slide_timer.stop()
        if self.display_window:
            self.display_window.clear_display()
        self.is_displaying = False
        self.update_show_clear_button_state()

    def close_application(self):
        logger.info("Attempting to close application...")
        self.slide_timer.stop()
        if self.editor_window and self.editor_window.isVisible():
            logger.debug("Closing editor window...")
            if not self.editor_window.close():
                logger.warning("Editor close cancelled, aborting application close.")
                return
        if self.display_window:
            logger.debug("Closing display window...")
            self.display_window.close()
        logger.debug("Closing control window...")
        self.close()
        logger.info("Quitting QApplication instance.")
        QCoreApplication.instance().quit()

    def closeEvent(self, event):
        logger.debug("ControlWindow closeEvent triggered.")
        self.slide_timer.stop()
        if self.display_window and self.display_window.isVisible():
            self.display_window.close()
        if self.editor_window and self.editor_window.isVisible():
            self.editor_window.close()
        super().closeEvent(event)
        logger.debug("ControlWindow closeEvent finished.")