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
# --- NEW IMPORT ---
from ..text.paragraph_manager import ParagraphManager
# --- END NEW IMPORT ---
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
        # --- NEW: ParagraphManager ---
        self.paragraph_manager = ParagraphManager()
        # --- END NEW ---
        self.current_index = -1
        self.is_displaying = False

        # --- NEW: Text State Variables ---
        self.current_paragraph_data = None # Holds the loaded paragraph dict
        self.current_sentence_index = -1 # 0-based index for sentences
        self.text_start_index = -1       # 0-based start index for current slide
        self.text_end_index = -1         # 0-based end index for current slide
        # --- END NEW ---

        self.editor_window = None
        self.settings_window_instance = None

        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)
        self.indicator_icons = self._load_indicator_icons()

        self.setup_ui()
        setup_keybindings(self, self.settings_manager)
        self.update_ui_state()
        self.load_last_playlist()
        logger.debug("ControlWindow initialization complete.")

    def _load_indicator_icons(self):
        # ... (This method remains unchanged) ...
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
        # ... (This method remains unchanged) ...
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


    def populate_playlist_view(self):
        # ... (This method remains unchanged) ...
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
        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")

    def _set_slide_index(self, new_index):
        # ... (This method remains unchanged) ...
        slides = self.playlist.get_slides()
        num_slides = len(slides)
        old_index = self.current_index
        changed = False

        if not slides:
            if self.current_index != -1:
                self.current_index = -1
                changed = True
                logger.debug(f"Playlist empty, index set to -1 from {old_index}")
        elif 0 <= new_index < num_slides:
            if self.current_index != new_index:
                self.current_index = new_index
                changed = True
                logger.debug(f"Slide index changed from {old_index} to {self.current_index}")
        else:
            if not (0 <= self.current_index < num_slides): # If current index is also bad
                 self.current_index = -1 if slides else -1 # Reset to -1
                 changed = (old_index != self.current_index)
            logger.warning(f"Requested index {new_index} is out of bounds (0-{num_slides-1}). Index remains {self.current_index}.")

        if changed:
            self.update_ui_state()
        return changed


    # --- NEW: Reset Text State ---
    def _reset_text_state(self):
        """Clears all internal text-related state variables."""
        logger.debug("Resetting text state.")
        self.current_paragraph_data = None
        self.current_sentence_index = -1
        self.text_start_index = -1
        self.text_end_index = -1
        if self.display_window:
             self.display_window.clearText() # Also clear renderer
    # --- END NEW ---


    # --- NEW: Display Current Sentence ---
    def _display_current_sentence(self):
        """Displays the sentence based on current_sentence_index."""
        if not self.current_paragraph_data or self.current_sentence_index < 0:
            logger.debug("_display_current_sentence called but no text active.")
            if self.display_window:
                self.display_window.clearText()
            return

        sentences = self.current_paragraph_data.get("sentences", [])
        if self.text_start_index <= self.current_sentence_index <= self.text_end_index:
            sentence_data = sentences[self.current_sentence_index]
            text = sentence_data.get("text", "")
            delay = sentence_data.get("delay_seconds", 0.0)
            logger.info(f"Displaying sentence {self.current_sentence_index + 1}: '{text}'")
            if self.display_window:
                self.display_window.displayText(text)
            # TODO: Implement timer logic based on 'delay' here later.
        else:
            logger.warning(f"Sentence index {self.current_sentence_index} out of range ({self.text_start_index}-{self.text_end_index}). Clearing text.")
            self._reset_text_state() # Clear if out of bounds

    # --- END NEW ---

    # --- MODIFIED: _display_current_slide ---
    def _display_current_slide(self):
        self.slide_timer.stop()
        self._reset_text_state() # Reset text state before displaying *any* slide

        slides = self.playlist.get_slides()

        if not (0 <= self.current_index < len(slides)):
            logger.warning(f"Cannot display: Invalid current_index {self.current_index}. Clearing display.")
            self.clear_display_screen()
            return

        logger.info(f"Displaying slide {self.current_index + 1}.")
        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data:
             logger.critical(f"INCONSISTENCY: No slide_data for valid index {self.current_index}. Clearing.")
             self.clear_display_screen()
             return

        # Display images first
        self.is_displaying = True
        self.display_window.display_images(slide_data.get("layers", []))

        # --- NEW: Handle Text Overlay ---
        text_overlay_info = slide_data.get("text_overlay")
        if text_overlay_info:
            para_name = text_overlay_info.get("paragraph_name")
            start_sent_1based = text_overlay_info.get("start_sentence")
            end_sent = text_overlay_info.get("end_sentence")

            if para_name and start_sent_1based and end_sent:
                try:
                    self.current_paragraph_data = self.paragraph_manager.load_paragraph(para_name)
                    if self.current_paragraph_data:
                        num_para_sentences = len(self.current_paragraph_data.get("sentences", []))
                        self.text_start_index = start_sent_1based - 1 # Convert to 0-based
                        if end_sent == "all":
                            self.text_end_index = num_para_sentences - 1
                        else:
                            self.text_end_index = end_sent - 1 # Convert to 0-based

                        # Validate indices
                        if 0 <= self.text_start_index < num_para_sentences and \
                           self.text_start_index <= self.text_end_index < num_para_sentences:
                           self.current_sentence_index = self.text_start_index
                           self._display_current_sentence() # Display the first sentence
                        else:
                           logger.error(f"Invalid sentence range ({start_sent_1based}-{end_sent}) for paragraph '{para_name}' ({num_para_sentences} sentences). No text shown.")
                           self._reset_text_state()
                    else:
                        logger.error(f"Failed to load paragraph '{para_name}'. No text shown.")
                        QMessageBox.warning(self, "Text Error", f"Could not load paragraph: {para_name}")
                except (FileNotFoundError, ValueError) as e:
                    logger.error(f"Error loading paragraph '{para_name}': {e}", exc_info=True)
                    QMessageBox.warning(self, "Text Error", f"Could not load paragraph '{para_name}':\n{e}")
                    self._reset_text_state()
            else:
                logger.warning(f"Slide {self.current_index + 1} has incomplete text_overlay data.")
        # --- END NEW ---

        # Start slide timer ONLY if no text is active (text handles its own timing later)
        if self.current_sentence_index == -1:
             duration = slide_data.get("duration", 0)
             if duration > 0:
                 self.slide_timer.start(duration)

        self.update_ui_state()
    # --- END MODIFIED ---


    def clear_display_screen(self):
        # --- MODIFIED: Ensure text state is reset ---
        self._reset_text_state()
        # --- END MODIFIED ---
        if not self.is_displaying and not self.slide_timer.is_active():
             return

        logger.info("Clearing display screen.")
        self.slide_timer.stop()
        if self.display_window:
            self.display_window.clear_display()
        self.is_displaying = False
        self.update_ui_state()


    def update_ui_state(self):
        # ... (This method remains unchanged) ...
        self.update_list_selection()
        self.update_show_clear_button_state()
        slides = self.playlist.get_slides()
        has_slides = bool(slides)
        num_slides = len(slides)

        self.prev_button.setEnabled(has_slides and (self.current_index > 0 or self.current_sentence_index > self.text_start_index))
        self.next_button.setEnabled(has_slides and (self.current_index < num_slides - 1 or self.current_sentence_index < self.text_end_index))
        self.show_clear_button.setEnabled(has_slides)


    def update_list_selection(self):
        # ... (This method remains unchanged) ...
        logger.debug(f"Updating list selection to index {self.current_index}.")
        item_to_select = None
        if self.playlist_view.count() > 0:
            for i in range(self.playlist_view.count()):
                item = self.playlist_view.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == self.current_index:
                    item_to_select = item
                    break
        try:
            self.playlist_view.currentItemChanged.disconnect(self.handle_list_selection)
        except (TypeError, RuntimeError):
            pass
        self.playlist_view.setCurrentItem(item_to_select)
        if item_to_select:
            self.playlist_view.scrollToItem(item_to_select, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.playlist_view.currentItemChanged.connect(self.handle_list_selection)


    def update_show_clear_button_state(self):
        # ... (This method remains unchanged) ...
        if self.is_displaying:
            self.show_clear_button.setText(" Clear")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("clear.png")))
            self.show_clear_button.setToolTip("Clear the display (Space or Esc)")
        else:
            self.show_clear_button.setText(" Show")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.show_clear_button.setToolTip("Show the selected slide (Space)")


    def handle_show_clear_click(self):
        # ... (This method remains unchanged) ...
        logger.debug("Show/Clear button clicked.")
        if self.is_displaying:
            self.clear_display_screen()
        else:
            slides = self.playlist.get_slides()
            if not slides:
                QMessageBox.information(self, "No Playlist", "Load a playlist to show a slide.")
                return
            if not (0 <= self.current_index < len(slides)):
                self._set_slide_index(0)
            self._display_current_slide()


    # --- MODIFIED: next_slide ---
    def next_slide(self):
        logger.debug("Next slide triggered.")

        # If text is currently active, try to advance the sentence first
        if self.current_sentence_index != -1 and self.current_paragraph_data:
            if self.current_sentence_index < self.text_end_index:
                self.current_sentence_index += 1
                self._display_current_sentence()
                self.update_ui_state() # Update button states
                return # Don't advance the slide yet

        # If we reached here, it means either no text was active,
        # or we just finished the last sentence. Proceed to next slide.
        self._reset_text_state() # Ensure text is cleared before next slide

        slides = self.playlist.get_slides()
        if not slides or not (0 <= self.current_index < len(slides) - 1):
            logger.info("Cannot go next: No slides or already at the end.")
            return

        self._set_slide_index(self.current_index + 1)
        self._display_current_slide() # This will handle displaying the new slide (and its text, if any)
    # --- END MODIFIED ---


    # --- MODIFIED: prev_slide ---
    def prev_slide(self):
        logger.debug("Previous slide triggered.")

        # If text is currently active and not the first sentence, go back one sentence
        if self.current_sentence_index != -1 and self.current_paragraph_data:
             if self.current_sentence_index > self.text_start_index:
                 self.current_sentence_index -= 1
                 self._display_current_sentence()
                 self.update_ui_state() # Update button states
                 return # Don't go to previous slide yet

        # If we reached here, it means either no text was active,
        # or we were at the first sentence. Proceed to previous slide.
        self._reset_text_state() # Ensure text is cleared before prev slide

        if not self.playlist.get_slides() or self.current_index <= 0:
            logger.info("Cannot go previous: No slides or already at the start.")
            return

        self._set_slide_index(self.current_index - 1)
        self._display_current_slide() # This will handle displaying the new slide (and its text, if any)
    # --- END MODIFIED ---


    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        # ... (This method remains unchanged) ...
        logger.debug("Slide list double-clicked.")
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if self._set_slide_index(index):
                self._display_current_slide()


    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        # ... (This method remains unchanged) ...
        logger.debug("List selection changed via UI.")
        if self.slide_timer.is_active():
            self.slide_timer.stop()
            logger.debug("Timer stopped due to list selection.")

        if current_item:
            self._set_slide_index(current_item.data(Qt.ItemDataRole.UserRole))
        else:
            self._set_slide_index(-1)


    def auto_advance_or_loop_slide(self):
        # --- MODIFIED: Check text first ---
        logger.debug("Timer triggered for auto-advance/loop.")
        # If text is active, this timer shouldn't be running (yet)
        # We will add sentence timing later. For now, assume this only
        # runs when a slide (without text) has a duration.
        if self.current_sentence_index != -1:
            logger.warning("Slide timer fired while text is active. This shouldn't happen yet. Stopping.")
            self.slide_timer.stop()
            return
        # --- END MODIFIED ---

        if not self.is_displaying:
            logger.warning("Timer fired but not displaying. Stopping timer.")
            self.slide_timer.stop()
            return

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data:
            logger.warning("No current slide data for timer. Clearing display.")
            self.clear_display_screen()
            return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)

        if loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                 if loop_target_0_based == self.current_index:
                      logger.debug(f"Slide {self.current_index + 1} loops to self. Advancing.")
                      if self.current_index < num_slides - 1:
                          self.next_slide() # Use next_slide now
                      else:
                          logger.info("Last slide looping to self. No further action.")
                          self.slide_timer.stop()
                 else:
                    logger.info(f"Looping to slide {loop_target_1_based}.")
                    self._set_slide_index(loop_target_0_based)
                    self._display_current_slide()
                 return
            else:
                 logger.warning(f"Invalid loop target ({loop_target_1_based}). Advancing instead.")

        if self.current_index < num_slides - 1:
            logger.info("Auto-advancing to next slide.")
            self.next_slide() # Use next_slide now
        else:
            logger.info("Timer expired on last slide, no loop/invalid loop. Stopping.")
            self.clear_display_screen()


    def load_playlist(self, file_path):
        # --- MODIFIED: Reset text state on load ---
        logger.info(f"Attempting to load playlist: {file_path}")
        self.slide_timer.stop()
        self._reset_text_state() # Reset text
        # --- END MODIFIED ---
        try:
            self.playlist.load(file_path)
            self.settings_manager.set_current_playlist(file_path)
            logger.info(f"Successfully loaded: {file_path}")
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load playlist {file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist()
            self.settings_manager.set_current_playlist(None)

        self.clear_display_screen()
        self.populate_playlist_view()
        self._set_slide_index(0 if self.playlist.get_slides() else -1)


    def load_playlist_dialog(self):
        # ... (This method remains unchanged) ...
        logger.debug("Opening load playlist dialog...")
        default_dir = get_playlists_path()
        fileName = get_themed_open_filename(self, "Open Playlist", default_dir, "JSON Files (*.json)")
        if fileName:
            self.load_playlist(fileName)


    def load_last_playlist(self):
        # ... (This method remains unchanged) ...
        last_playlist = self.settings_manager.get_current_playlist()
        if last_playlist:
            logger.info(f"Loading last used playlist: {last_playlist}")
            self.load_playlist(last_playlist)
        else:
            logger.info("No last playlist found in settings.")
            self.clear_display_screen()


    def open_playlist_editor(self):
        # ... (This method remains unchanged) ...
        logger.info("Opening playlist editor...")
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(self.display_window, self.playlist, self)
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()


    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        # ... (This method remains unchanged) ...
        logger.info(f"ControlWindow received signal to reload: {saved_playlist_path}")
        self.load_playlist(saved_playlist_path)


    def open_settings_window(self):
        # ... (This method remains unchanged) ...
        logger.info("Opening settings window...")
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            self.settings_window_instance = SettingsWindow(self)
            self.settings_window_instance.show()
        else:
            self.settings_window_instance.activateWindow()
            self.settings_window_instance.raise_()


    def toggle_display_window_visibility(self):
        # ... (This method remains unchanged) ...
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
        # ... (This method remains unchanged) ...
        logger.info("Close application action initiated...")
        self.close()


    def closeEvent(self, event):
        # ... (This method remains unchanged) ...
        logger.debug("ControlWindow closeEvent triggered.")
        self.slide_timer.stop()

        if self.editor_window and self.editor_window.isVisible():
            logger.debug("Attempting to close PlaylistEditorWindow...")
            if not self.editor_window.close():
                logger.warning("PlaylistEditorWindow close cancelled, aborting application quit.")
                event.ignore()
                return

        if self.settings_window_instance and self.settings_window_instance.isVisible():
            logger.debug("Closing SettingsWindow...")
            self.settings_window_instance.close()
        if self.display_window and self.display_window.isVisible():
            logger.debug("Closing DisplayWindow...")
            self.display_window.close()

        logger.info("ControlWindow accepted close. Quitting QApplication.")
        QCoreApplication.instance().quit()
        event.accept()