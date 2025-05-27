# myapp/gui/control_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QListWidget, QListWidgetItem, QHBoxLayout, QApplication,
    QListView, QAbstractItemView
)
from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

# Local Imports
from .file_dialog_helpers import get_themed_open_filename
from .playlist_editor import PlaylistEditorWindow
from .settings_window import SettingsWindow
from ..playlist.playlist import Playlist
from ..utils.paths import get_icon_file_path, get_playlists_path
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

        # Set Application Icon
        try:
            icon_name = "app_icon.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                logger.warning(f"Window icon '{icon_name}' not found.")
        except (OSError, IOError) as e:
             logger.error(f"Failed to set window icon due to OS/IO error: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}", exc_info=True)

        self.display_window = display_window
        if not display_window:
            logger.critical("DisplayWindow instance must be provided.")
            raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager()
        self.playlist = Playlist()
        self.current_index = -1 # Start with no slide selected
        self.is_displaying = False # Start with nothing on screen

        self.editor_window = None
        self.settings_window_instance = None

        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)

        self.indicator_icons = self._load_indicator_icons()

        self.setup_ui()
        setup_keybindings(self, self.settings_manager)
        self.update_ui_state() # Use a single method to set initial UI
        self.load_last_playlist()
        logger.debug("ControlWindow initialization complete.")

    def _load_indicator_icons(self):
        logger.debug("Loading indicator icons...")
        icons = {}
        icon_files = { "slide": "slide_icon.png", "timer": "timer_icon.png", "loop": "loop_icon.png" }
        size = 16
        for name, filename in icon_files.items():
            try:
                path = get_icon_file_path(filename)
                if not path or not os.path.exists(path):
                     logger.warning(f"Indicator icon file not found: {filename}")
                     icons[name] = QPixmap()
                     continue
                pixmap = QPixmap(path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if pixmap.isNull():
                    logger.warning(f"Failed to load or scale indicator icon '{filename}'.")
                    icons[name] = QPixmap()
                else:
                    icons[name] = pixmap
            except (OSError, IOError) as e:
                logger.error(f"OS/IO Error loading indicator icon '{filename}': {e}", exc_info=True)
                icons[name] = QPixmap()
            except Exception as e:
                logger.critical(f"Unexpected error loading indicator icon '{filename}': {e}", exc_info=True)
                icons[name] = QPixmap()
        return icons

    def setup_ui(self):
        # ... (UI setup remains largely the same, ensure buttons exist) ...
        logger.debug("Setting up ControlWindow UI...")
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        playlist_buttons_layout = QHBoxLayout()
        self.load_button = create_button(" Load", "load.png", "Load a playlist (Ctrl+L)", self.load_playlist_dialog)
        self.edit_button = create_button(" Edit", "edit.png", "Open the Playlist Editor (Ctrl+E)", self.open_playlist_editor)
        self.settings_button = create_button(" Settings", "settings.png", "Open Application Settings", self.open_settings_window)
        self.toggle_display_button = create_button("Show Display", "show_display.png", "Show or Hide the Display Window", self.toggle_display_window_visibility)
        self.close_button = create_button(" Close", "close.png", "Close the application (Ctrl+Q)", self.close_application)

        playlist_buttons_layout.addWidget(self.load_button)
        playlist_buttons_layout.addWidget(self.edit_button)
        playlist_buttons_layout.addWidget(self.settings_button)
        playlist_buttons_layout.addStretch()
        playlist_buttons_layout.addWidget(self.toggle_display_button)
        playlist_buttons_layout.addWidget(self.close_button)
        main_layout.addLayout(playlist_buttons_layout)

        self.playlist_view = QListWidget()
        self.playlist_view.setViewMode(QListView.ViewMode.IconMode)
        self.playlist_view.setFlow(QListView.Flow.LeftToRight)
        # ... (Rest of playlist_view setup) ...
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
        self.prev_button = create_button(" Prev", "previous.png", "Previous slide (Arrow Keys, Page Up/Down)", self.prev_slide)
        self.next_button = create_button(" Next", "next.png", "Next slide (Arrow Keys, Page Up/Down)", self.next_slide)
        playback_buttons_layout.addWidget(self.show_clear_button)
        playback_buttons_layout.addWidget(self.prev_button)
        playback_buttons_layout.addWidget(self.next_button)
        main_layout.addLayout(playback_buttons_layout)

        self.setCentralWidget(central_widget)
        self.resize(600, 350)
        logger.debug("ControlWindow UI setup complete.")

    # --- Core State Transition Methods ---

    def _set_slide_index(self, new_index):
        """
        Safely sets the current_index, ensuring it's valid or -1.
        Returns True if the index changed, False otherwise.
        """
        slides = self.playlist.get_slides()
        num_slides = len(slides)

        old_index = self.current_index
        target_index = new_index

        if not slides:
            target_index = -1
        elif not (0 <= new_index < num_slides):
            logger.warning(f"Requested index {new_index} out of bounds. Setting to -1 or keeping current.")
            target_index = self.current_index if (0 <= self.current_index < num_slides) else -1

        if target_index != old_index:
            self.current_index = target_index
            logger.debug(f"Slide index changed from {old_index} to {self.current_index}")
            self.update_ui_state() # Update UI whenever index changes
            return True
        return False

    def _display_current_slide(self):
        """
        Stops timer, validates index, and updates the display window.
        Sets is_displaying = True if successful.
        """
        self.slide_timer.stop()
        slides = self.playlist.get_slides()

        if not (0 <= self.current_index < len(slides)):
            logger.warning(f"Cannot display: Invalid index {self.current_index} or no slides.")
            self.clear_display_screen()
            return

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: # Should not happen if index is valid, but good check
            logger.error(f"Inconsistency: No slide data for valid index {self.current_index}")
            self.clear_display_screen()
            return

        logger.info(f"Displaying slide {self.current_index + 1}.")
        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        self.is_displaying = True
        self.display_window.display_images(slide_data.get("layers", []))

        duration = slide_data.get("duration", 0)
        if duration > 0:
            self.slide_timer.start(duration)

        self.update_ui_state()

    def clear_display_screen(self):
        """Stops timer, clears display, sets is_displaying = False."""
        if not self.is_displaying and not self.slide_timer.is_active():
             return # Already clear

        logger.info("Clearing display screen.")
        self.slide_timer.stop()
        if self.display_window:
            self.display_window.clear_display()
        self.is_displaying = False
        self.update_ui_state()

    def update_ui_state(self):
        """Updates list selection and button states based on current state."""
        self.update_list_selection()
        self.update_show_clear_button_state()
        # Add updates for prev/next button enabled state if needed
        slides = self.playlist.get_slides()
        has_slides = bool(slides)
        self.prev_button.setEnabled(has_slides and self.current_index > 0)
        self.next_button.setEnabled(has_slides and self.current_index < len(slides) - 1)
        self.show_clear_button.setEnabled(has_slides)


    def update_list_selection(self):
        """Updates the visual selection in the QListWidget."""
        logger.debug(f"Updating list selection to index {self.current_index}.")
        item_to_select = None
        for i in range(self.playlist_view.count()):
            item = self.playlist_view.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.current_index:
                item_to_select = item
                break

        # Disconnect to prevent handle_list_selection loop, then reconnect
        try:
            self.playlist_view.currentItemChanged.disconnect(self.handle_list_selection)
        except (TypeError, RuntimeError): # If not connected (e.g. during setup)
            pass

        self.playlist_view.setCurrentItem(item_to_select)
        if item_to_select:
            self.playlist_view.scrollToItem(item_to_select, QAbstractItemView.ScrollHint.PositionAtCenter)

        self.playlist_view.currentItemChanged.connect(self.handle_list_selection)


    def update_show_clear_button_state(self):
        """Updates the 'Show/Clear' button icon and text."""
        if self.is_displaying:
            self.show_clear_button.setText(" Clear")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("clear.png")))
            self.show_clear_button.setToolTip("Clear the display (Space or Esc)")
        else:
            self.show_clear_button.setText(" Show")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.show_clear_button.setToolTip("Show the selected slide (Space)")

    # --- User Action Handlers ---

    def handle_show_clear_click(self):
        logger.debug("Show/Clear button clicked.")
        if self.is_displaying:
            self.clear_display_screen()
        else:
            slides = self.playlist.get_slides()
            if not slides:
                QMessageBox.information(self, "No Playlist", "Load a playlist to show a slide.")
                return
            # If no valid selection, set to 0 before displaying
            if not (0 <= self.current_index < len(slides)):
                self._set_slide_index(0)

            self._display_current_slide()

    def next_slide(self):
        logger.debug("Next slide triggered.")
        slides = self.playlist.get_slides()
        if not slides or self.current_index >= len(slides) - 1:
            logger.info("Cannot go next: No slides or already at the end.")
            return
        self._set_slide_index(self.current_index + 1)
        self._display_current_slide()

    def prev_slide(self):
        logger.debug("Previous slide triggered.")
        if self.current_index <= 0:
            logger.info("Cannot go previous: Already at the start or no selection.")
            return
        self._set_slide_index(self.current_index - 1)
        self._display_current_slide()

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        logger.debug("Slide list double-clicked.")
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            self._set_slide_index(index)
            self._display_current_slide()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        logger.debug("List selection changed via UI.")
        if self.slide_timer.is_active():
            self.slide_timer.stop()
            logger.debug("Timer stopped due to list selection.")
            # Optionally clear display or keep it? Keeping it seems less jarring.
            # self.is_displaying = False # If we want click to stop display
            # self.update_ui_state()

        if current_item:
            self._set_slide_index(current_item.data(Qt.ItemDataRole.UserRole))
        else:
            self._set_slide_index(-1)

    def auto_advance_or_loop_slide(self):
        logger.debug("Timer triggered for auto-advance/loop.")
        if not self.is_displaying: # Should not happen, but a good guard
            logger.debug("Display not active, timer ignored.")
            return

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)

        if loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                 logger.info(f"Looping to slide {loop_target_1_based}.")
                 self._set_slide_index(loop_target_0_based)
                 self._display_current_slide()
                 return
            else:
                 logger.warning(f"Invalid loop target ({loop_target_1_based}). Advancing instead.")

        # If no loop, or loop invalid, or loop to self -> advance
        if self.current_index < num_slides - 1:
            logger.info("Auto-advancing to next slide.")
            self._set_slide_index(self.current_index + 1)
            self._display_current_slide()
        else:
            logger.info("Timer expired on last slide, no loop. Stopping.")
            self.clear_display_screen() # Or maybe just stop? Clearing seems safer.

    def load_playlist(self, file_path):
        logger.info(f"Attempting to load playlist: {file_path}")
        self.slide_timer.stop() # Stop timer before loading
        try:
            self.playlist.load(file_path)
            self.settings_manager.set_current_playlist(file_path)
            logger.info(f"Successfully loaded: {file_path}")
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load playlist {file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist() # Reset to empty
            self.settings_manager.set_current_playlist(None)

        # Always reset state after loading (success or fail)
        self.clear_display_screen()
        self.populate_playlist_view() # This will repopulate
        self._set_slide_index(0 if self.playlist.get_slides() else -1) # Set index & update UI
        self.update_ui_state() # Ensure buttons etc are correct


    def load_playlist_dialog(self):
        logger.debug("Opening load playlist dialog...")
        default_dir = get_playlists_path()
        fileName = get_themed_open_filename(self, "Open Playlist", default_dir, "JSON Files (*.json)")
        if fileName:
            self.load_playlist(fileName)

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

        # This call was moved to update_ui_state, which is called by load_playlist later
        # self.update_list_selection()
        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")

    def load_last_playlist(self):
        last_playlist = self.settings_manager.get_current_playlist()
        if last_playlist:
            logger.info(f"Loading last used playlist: {last_playlist}")
            self.load_playlist(last_playlist)
        else:
            logger.info("No last playlist found in settings.")
            self.clear_display_screen() # Ensure clear state

    # --- Window Management ---
    def open_playlist_editor(self):
        logger.info("Opening playlist editor...")
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(self.display_window, self.playlist, self)
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        logger.info(f"ControlWindow received signal to reload: {saved_playlist_path}")
        self.load_playlist(saved_playlist_path)

    def open_settings_window(self):
        logger.info("Opening settings window...")
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            self.settings_window_instance = SettingsWindow(self)
            self.settings_window_instance.show()
        else:
            self.settings_window_instance.activateWindow()
            self.settings_window_instance.raise_()

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

    def close_application(self):
        logger.info("Attempting to close application...")
        self.close() # Trigger closeEvent

    def closeEvent(self, event):
        logger.debug("ControlWindow closeEvent triggered.")
        self.slide_timer.stop()

        # Try to close child windows gracefully
        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close(): # Let it prompt for save if needed
                logger.warning("Editor close cancelled, aborting application close.")
                event.ignore()
                return
        if self.settings_window_instance and self.settings_window_instance.isVisible():
             self.settings_window_instance.close()
        if self.display_window:
            self.display_window.close()

        logger.info("Quitting QApplication instance.")
        QCoreApplication.instance().quit()
        event.accept()