# myapp/gui/control_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QListWidget, QListWidgetItem, QHBoxLayout, QApplication,
    QListView, QAbstractItemView, QLabel
)
from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

# Local Imports
from .playlist_editor import PlaylistEditorWindow
from .settings_window import SettingsWindow
# AudioProgramEditorWindow is NOT imported here directly for opening
from ..playlist.playlist import Playlist
from ..text.paragraph_manager import ParagraphManager
from ..utils.paths import get_icon_file_path
from ..settings.settings_manager import SettingsManager
from myapp.settings.key_bindings import setup_keybindings
from myapp import __version__
from .thumbnail_generator import create_composite_thumbnail, get_thumbnail_size, get_list_widget_height
from .slide_timer import SlideTimer
from .widget_helpers import create_button
from .playlist_validator import PlaylistValidator
from .text_controller import TextController
from .playlist_io_handler import PlaylistIOHandler
from .ui_updater import ControlWindowUIUpdater

logger = logging.getLogger(__name__)


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        logger.debug("Initializing ControlWindow...")
        self.setWindowTitle(f"Control Window v{__version__}")

        try:
            icon_name = "app_icon.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}")

        self.display_window = display_window
        if not display_window: raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager()
        self.playlist = Playlist()
        self.paragraph_manager = ParagraphManager()
        self.playlist_validator = PlaylistValidator(self.paragraph_manager)
        self.text_controller = TextController(self.paragraph_manager, self.display_window)
        self.playlist_io = PlaylistIOHandler(self, self.settings_manager)
        self.ui_updater = ControlWindowUIUpdater(self)

        self.current_index = -1
        self.is_displaying = False
        self._is_timer_for_initial_text_delay = False

        self.editor_window = None  # This is for PlaylistEditorWindow
        self.settings_window_instance = None
        # self.audio_editor_window_instance = None # This was removed as per your request

        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)

        self.text_controller.finished_and_should_advance_slide.connect(self._handle_text_finished_advance)

        self.indicator_icons = self._load_indicator_icons()
        self.setup_ui()
        setup_keybindings(self, self.settings_manager)
        self.ui_updater.update_all()  # Initial UI state based on defaults
        self.load_last_playlist()  # Load last playlist and update UI accordingly
        logger.debug("ControlWindow initialization complete.")

    def _load_indicator_icons(self):
        logger.debug("Loading indicator icons...")
        icons = {}
        icon_files = {
            "slide": "slide_icon.png",
            "timer": "timer_icon.png",
            "loop": "loop_icon.png",
            "text": "text.png"
            # Later, you might add an "audio" indicator here
        }
        size = 16  # Desired icon size for the indicators
        for name, filename in icon_files.items():
            try:
                path = get_icon_file_path(filename)
                if not path or not os.path.exists(path):
                    logger.warning(f"Indicator icon file not found: {filename}")
                    icons[name] = QPixmap()  # Store an empty QPixmap as placeholder
                    continue
                pixmap = QPixmap(path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                if pixmap.isNull():
                    logger.warning(f"Failed to load or scale indicator icon '{filename}'.")
                    icons[name] = QPixmap()
                else:
                    icons[name] = pixmap
            except Exception as e:
                logger.critical(f"Unexpected error loading indicator icon '{filename}': {e}", exc_info=True)
                icons[name] = QPixmap()
        return icons

    def setup_ui(self):
        logger.debug("Setting up ControlWindow UI...")
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        top_buttons_layout = QHBoxLayout()
        self.load_button = create_button(" Load Playlist", "load.png", "Load a playlist (Ctrl+L)",
                                         self.load_playlist_dialog)
        self.edit_playlist_button = create_button(" Edit Playlist", "edit.png", "Open the Playlist Editor (Ctrl+E)",
                                                  self.open_playlist_editor)
        # No "Edit Audio" button here
        self.settings_button = create_button(" Settings", "settings.png", "Open Application Settings",
                                             self.open_settings_window)

        self.issue_label = QLabel("")
        self.issue_label.setStyleSheet("color: red; font-weight: bold;")
        self.issue_icon_widget = QWidget()
        self.issue_icon_layout = QHBoxLayout(self.issue_icon_widget)
        self.issue_icon_layout.setContentsMargins(0, 0, 0, 0)
        self.issue_icon_layout.setSpacing(2)

        self.close_app_button = create_button(" Close App", "close.png", "Close the application (Ctrl+Q)",
                                              self.close_application)

        top_buttons_layout.addWidget(self.load_button)
        top_buttons_layout.addWidget(self.edit_playlist_button)
        top_buttons_layout.addWidget(self.settings_button)
        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(self.issue_label)
        top_buttons_layout.addWidget(self.issue_icon_widget)
        top_buttons_layout.addWidget(self.close_app_button)
        main_layout.addLayout(top_buttons_layout)

        self.playlist_view = QListWidget()
        self.playlist_view.setViewMode(QListView.ViewMode.IconMode)
        self.playlist_view.setFlow(QListView.Flow.LeftToRight)
        self.playlist_view.setMovement(QListView.Movement.Static)  # Items are not draggable in ControlWindow
        self.playlist_view.setResizeMode(QListView.ResizeMode.Adjust)  # Adjust to content
        self.playlist_view.setWrapping(False)  # Horizontal scroll instead of wrapping
        self.playlist_view.setIconSize(get_thumbnail_size())
        self.playlist_view.setFixedHeight(get_list_widget_height())  # Fixed height for the thumbnail strip
        self.playlist_view.setSpacing(5)  # Spacing between thumbnails
        self.playlist_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlist_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.playlist_view.currentItemChanged.connect(self.handle_list_selection)
        self.playlist_view.itemDoubleClicked.connect(self.go_to_selected_slide_from_list)
        main_layout.addWidget(self.playlist_view)

        playback_buttons_layout = QHBoxLayout()
        self.show_clear_button = QPushButton()  # Text/Icon set by UI updater
        self.show_clear_button.clicked.connect(self.handle_show_clear_click)

        self.toggle_display_button = create_button("Show Display", "show_display.png",
                                                   "Show or Hide the Display Window",
                                                   self.toggle_display_window_visibility)
        self.prev_button = create_button(" Prev", "previous.png", "Previous slide/sentence (Arrow Keys, Page Up/Down)",
                                         self.prev_slide)
        self.next_button = create_button(" Next", "next.png", "Next slide/sentence (Arrow Keys, Page Up/Down)",
                                         self.next_slide)

        playback_buttons_layout.addWidget(self.show_clear_button)
        playback_buttons_layout.addWidget(self.toggle_display_button)
        playback_buttons_layout.addStretch()
        playback_buttons_layout.addWidget(self.prev_button)
        playback_buttons_layout.addWidget(self.next_button)
        main_layout.addLayout(playback_buttons_layout)

        self.setCentralWidget(central_widget)
        self.resize(700, 350)  # Initial size, can be adjusted
        logger.debug("ControlWindow UI setup complete.")
        self.ui_updater.update_issue_display([])  # Initialize with no issues shown

    def populate_playlist_view(self):
        logger.debug("Populating playlist view...")
        self.playlist_view.clear()  # Clears previous items

        for i, slide_data in enumerate(self.playlist.get_slides()):
            text_overlay_info = slide_data.get("text_overlay")
            if not isinstance(text_overlay_info, dict):
                text_overlay_info = {}
            has_text = bool(text_overlay_info.get("paragraph_name"))
            # has_audio = bool(slide_data.get("audio_program_name")) # For future use

            composite_icon = create_composite_thumbnail(
                slide_data,
                i,
                self.indicator_icons,
                has_text_overlay=has_text
                # has_audio_program=has_audio # Pass this when audio is integrated
            )
            item = QListWidgetItem(composite_icon, "")  # No text label for icon mode items

            tooltip_parts = [f"Slide {i + 1}"]
            duration = slide_data.get("duration", 0)
            loop_target = slide_data.get("loop_to_slide", 0)

            if has_text:
                tooltip_parts.append(f"Initial Text Delay: {duration}s")
            elif duration > 0:  # No text, but has duration
                tooltip_parts.append(f"Plays for: {duration}s")
            else:  # No text, no duration
                tooltip_parts.append("Manual advance")

            if loop_target > 0:  # Loop target is 1-based
                # A loop is only active if there's some timing mechanism (slide duration or text timing)
                is_slide_timed = duration > 0
                is_text_timed = has_text and text_overlay_info.get("sentence_timing_enabled", False)
                if is_slide_timed or is_text_timed:
                    tooltip_parts.append(f"Loops to: Slide {loop_target}")
                else:
                    tooltip_parts.append(
                        f"Loop to Slide {loop_target} (inactive due to 0s duration/delay or no timed text)")

            if has_text:
                tooltip_parts.append(f"Text: {text_overlay_info.get('paragraph_name', 'N/A')}")
                if text_overlay_info.get("sentence_timing_enabled"):
                    tooltip_parts.append("Timed Sentences")
                if text_overlay_info.get("auto_advance_slide"):
                    tooltip_parts.append("Auto->Next Slide after text")

            # TODO: Add audio program name to tooltip when integrated

            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store slide index
            self.playlist_view.addItem(item)

        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")
        issues = self.playlist_validator.validate(self.playlist)
        self.ui_updater.update_issue_display(issues)

    def _handle_text_finished_advance(self):
        logger.info("TextController signaled to advance to next slide.")
        self.text_controller.reset()  # Reset text state before moving

        slides = self.playlist.get_slides()
        # Check if there is a next slide
        if self.current_index < len(slides) - 1:
            self._set_slide_index(self.current_index + 1)
            self._display_current_slide()
        else:  # It was the last slide
            logger.info("Text finished on the last slide, no next slide to auto-advance to.")
            self.is_displaying = True  # Keep images if any
            if self.display_window: self.display_window.clearText()  # Clear only text
            self.text_controller.reset()  # Ensure it's fully reset

        self.ui_updater.update_all()

    def _set_slide_index(self, new_index):
        slides = self.playlist.get_slides()
        num_slides = len(slides)
        old_index = self.current_index
        changed = False

        if not slides:  # No slides in playlist
            if self.current_index != -1: self.current_index = -1; changed = True
        elif 0 <= new_index < num_slides:  # Valid new index
            if self.current_index != new_index: self.current_index = new_index; changed = True
        elif not (0 <= self.current_index < num_slides):  # current_index was invalid (e.g. -1 or too high)
            self.current_index = -1 if not slides else 0;  # Go to 0 if slides exist, else -1
            changed = (old_index != self.current_index)
        # If new_index is out of bounds but current_index is valid, current_index remains. No change.

        if changed:
            self.ui_updater.update_all()  # Update UI if index actually changed
        return changed

    def _display_current_slide(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        # TODO: Stop audio playback if/when new audio system is active and playing
        self._is_timer_for_initial_text_delay = False

        slides = self.playlist.get_slides()
        if not (0 <= self.current_index < len(slides)):
            self.clear_display_screen();  # Clear if index is invalid
            return

        logger.info(f"Displaying slide {self.current_index + 1}.")
        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()  # Ensure display is visible

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data:  # Should not happen if index is valid, but good check
            logger.warning(f"Slide data is None for valid index {self.current_index}, clearing.")
            self.clear_display_screen();
            return

        self.is_displaying = True  # Indicates something (images/text) is on screen
        self.display_window.display_images(slide_data.get("layers", []))

        # TextController's load_slide_text will handle getting text_overlay and its settings
        can_show_text, initial_delay_for_text = self.text_controller.load_slide_text(slide_data)

        # TODO: Later, add logic here to load and play an audio program if specified in slide_data
        # This would involve interacting with an audio player component.
        # The slide_timer might then be controlled by audio duration or text duration,
        # or a combination.

        if can_show_text:
            if initial_delay_for_text > 0:
                logger.info(
                    f"Starting initial text delay of {initial_delay_for_text}s for slide {self.current_index + 1}.")
                self._is_timer_for_initial_text_delay = True
                self.slide_timer.start(initial_delay_for_text)
            else:  # No initial delay, show text immediately
                logger.info("No initial text delay. Showing first sentence immediately.")
                self.text_controller.show_first_sentence()
        else:  # No text, or text failed to load
            slide_duration_no_text = slide_data.get("duration", 0)
            if slide_duration_no_text > 0:  # Only start slide timer if there's a duration and no text to manage timing
                logger.debug(
                    f"Starting slide duration timer of {slide_duration_no_text}s for slide {self.current_index + 1} (no text).")
                self.slide_timer.start(slide_duration_no_text)

        self.ui_updater.update_all()

    def clear_display_screen(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        # TODO: Stop audio playback here too when integrated
        self._is_timer_for_initial_text_delay = False
        if self.display_window: self.display_window.clear_display()
        self.is_displaying = False
        self.ui_updater.update_all()

    def handle_show_clear_click(self):
        # TODO: This logic will get more complex with Play/Pause for audio
        if self.is_displaying or self.text_controller.is_active():  # If something is showing
            self.clear_display_screen()
        else:  # Nothing is showing, so show current or first slide
            slides = self.playlist.get_slides()
            if not slides: QMessageBox.information(self, "No Playlist", "Load a playlist..."); return
            if not (0 <= self.current_index < len(slides)): self._set_slide_index(
                0)  # Default to first slide if current is invalid
            self._display_current_slide()

    def next_slide(self):
        # TODO: If audio is playing and synced, "next" might mean "next audio segment" or "skip audio and go next"
        logger.debug("ControlWindow: next_slide called")
        self.text_controller.stop_sentence_timer()  # Stop sentence timer if active

        if self.text_controller.is_active():
            if self.text_controller.show_next_sentence():  # Try to advance text sentence
                self.ui_updater.update_all();
                return  # Text advanced, stay on slide
            else:  # Text was active but finished all its sentences
                self.text_controller.reset()  # Reset text controller before slide change

        # Proceed to change slide if text is not active or finished its part
        slides = self.playlist.get_slides()
        if not slides or not (self.current_index < len(slides) - 1):  # If no slides or at the last slide
            logger.info("Cannot go next: No more slides or playlist empty.")
            self.ui_updater.update_all();
            return  # Update UI (e.g., disable next button)

        self._set_slide_index(self.current_index + 1)
        self._display_current_slide()

    def prev_slide(self):
        # TODO: Similar to next_slide, consider audio impact. Does "prev" restart audio or go to prev audio segment?
        logger.debug("ControlWindow: prev_slide called")
        self.text_controller.stop_sentence_timer()

        if self.text_controller.is_active():
            if self.text_controller.show_prev_sentence():  # Try to go to previous sentence
                self.ui_updater.update_all();
                return  # Text moved back, stay on slide
            else:  # At start of text or text not active for prev
                self.text_controller.reset()  # Reset before slide change

        # Proceed to change to previous slide
        if not self.playlist.get_slides() or self.current_index <= 0:  # If no slides or at the first slide
            logger.info("Cannot go previous: No slides or already at the start.")
            self.ui_updater.update_all();
            return

        self._set_slide_index(self.current_index - 1)
        self._display_current_slide()

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            # Only display if index actually changed or if it's re-selected and not showing
            if self.current_index != index or not (self.is_displaying or self.text_controller.is_active()):
                if self._set_slide_index(index):  # If index changed
                    self._display_current_slide()
            elif self.current_index == index:  # If same slide is double-clicked, ensure it's shown (or re-shown)
                self._display_current_slide()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        logger.debug(
            f"List selection changed. Current: {current_item.data(Qt.ItemDataRole.UserRole) if current_item else 'None'}")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()
        # TODO: Stop audio if selection changes and audio was playing

        if current_item:
            new_idx = current_item.data(Qt.ItemDataRole.UserRole)
            if self.current_index != new_idx:  # Only reset display state if index actually changes
                self.is_displaying = False  # Mark as not displaying until _display_current_slide is called
                self.text_controller.reset()
                if self.display_window: self.display_window.clearText()  # Clear only text initially
            self._set_slide_index(new_idx)  # This will call ui_updater.update_all()
            # Note: We don't auto-display on selection here; user must press Show or double-click.
        else:  # No item selected (e.g. list cleared)
            self._set_slide_index(-1)
            self.clear_display_screen()  # This will also call ui_updater.update_all()
        # ui_updater.update_all() is called by _set_slide_index or clear_display_screen

    def auto_advance_or_loop_slide(self):
        logger.debug(f"Main SlideTimer timeout. For initial text delay: {self._is_timer_for_initial_text_delay}")

        if self._is_timer_for_initial_text_delay:  # Timer was for text delay
            self._is_timer_for_initial_text_delay = False  # Reset flag
            if self.text_controller.is_active():  # is_active means text was loaded
                logger.info("Initial text delay timer expired. Showing first sentence.")
                self.text_controller.show_first_sentence()
                # Sentence controller will now manage its own timing or wait for manual advance
            else:
                # This might happen if text_overlay was defined but paragraph was missing/empty
                logger.warning(
                    "Initial text delay timer expired, but no text active in TextController (e.g. paragraph missing).")
                # Potentially advance slide here if that's desired behavior for "failed text"
            return  # Don't advance slide yet, let text controller manage its part

        # If timer was not for text delay, it was for slide duration
        # TODO: If audio is playing and dictating slide end, this logic needs adjustment.
        # This current logic assumes no audio or audio is background.

        # If text is active and has its own sentence timing, the slide_timer might be for overall max duration.
        # However, if text is advancing sentence-by-sentence by its own timers, this slide_timer might conflict
        # or be redundant unless it's meant as a hard cut-off.
        if self.text_controller.is_active() and self.text_controller._sentence_timing_enabled:
            logger.debug(
                "Slide duration timer fired, but text controller is active with its own sentence timing. Ignoring for slide advance here; text controller will signal if it wants to advance slide.")
            # The text_controller will emit `finished_and_should_advance_slide` if auto_advance_slide is true for it.
            return

        if not self.is_displaying:  # If images are not showing, this timer is irrelevant.
            logger.warning("Slide duration timer fired but main display (is_displaying) is false. Stopping.");
            return

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: self.clear_display_screen(); return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)

        if loop_target_1_based > 0:  # If a loop target is set
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                logger.info(f"Slide timer: Looping to slide {loop_target_1_based}.")
                self._set_slide_index(loop_target_0_based)
                self._display_current_slide();
                return
            else:  # Invalid loop target
                logger.warning(f"Slide timer: Invalid loop target ({loop_target_1_based}). Advancing if possible.")

        # No loop or invalid loop, try to advance to next slide
        if self.current_index < num_slides - 1:
            logger.info("Slide timer: Auto-advancing to next slide.")
            self.next_slide()  # This will call _display_current_slide
        else:  # At the last slide, no loop
            logger.info("Slide timer: Expired on last slide, no loop. Clearing display.")
            self.clear_display_screen()

    def _load_and_update_playlist(self, file_path: str):
        self.clear_display_screen()  # Clear previous state
        try:
            self.playlist.load(file_path)
            self.settings_manager.set_current_playlist(file_path)
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist()  # Reset to empty
            self.settings_manager.set_current_playlist(None)

        self.populate_playlist_view()  # Ensure this method exists and is correct
        self._set_slide_index(0 if self.playlist.get_slides() else -1)  # Select first or none
        self.ui_updater.update_all()

    def load_playlist_dialog(self):
        file_path = self.playlist_io.prompt_load_playlist()
        if file_path: self._load_and_update_playlist(file_path)

    def load_last_playlist(self):
        file_path = self.playlist_io.get_last_playlist_path()
        if file_path:
            logger.info(f"Attempting to load last playlist: {file_path}")
            self._load_and_update_playlist(file_path)
        else:  # No last playlist or it was invalid
            logger.info("No valid last playlist found. Starting with empty setup.")
            self.populate_playlist_view()  # Show empty list
            self.clear_display_screen()  # Ensure display is clear
            self.ui_updater.update_all()  # Ensure UI reflects empty state

    def open_playlist_editor(self):  # This is the existing method for playlist editing
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(self.display_window, self.playlist, self)
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow();
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        # This is called when playlist editor saves, reload it in control window
        logger.info(f"Playlist saved by editor, reloading: {saved_playlist_path}")
        self._load_and_update_playlist(saved_playlist_path)

    def open_settings_window(self):
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            self.settings_window_instance = SettingsWindow(self)
            self.settings_window_instance.show()
        else:
            self.settings_window_instance.activateWindow();
            self.settings_window_instance.raise_()

    def toggle_display_window_visibility(self):
        if self.display_window:
            if self.display_window.isVisible():
                self.display_window.hide()
                self.toggle_display_button.setText("Show Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png")))
            else:
                # Logic to determine which screen and set geometry
                screens = QApplication.instance().screens()
                if screens:
                    # Default to secondary screen if available, else primary
                    target_screen = screens[1] if len(screens) > 1 else screens[0]
                    self.display_window.setGeometry(target_screen.geometry())
                self.display_window.showFullScreen()  # Or .show() if you prefer windowed
                self.toggle_display_button.setText("Hide Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("hide_display.png")))

    def close_application(self):
        self.close()  # Triggers closeEvent

    def closeEvent(self, event):
        logger.info("ControlWindow closeEvent triggered.")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()
        # TODO: Stop audio player here when audio playback is integrated

        # Close editor windows if they are open and allow them to prompt for save
        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close():  # close() returns False if user cancels
                logger.info("Playlist editor close cancelled, aborting ControlWindow close.")
                event.ignore();
                return

        # Note: AudioProgramEditorWindow is managed by PlaylistEditorWindow,
        # so its closure should be handled when PlaylistEditorWindow closes.

        if self.settings_window_instance and self.settings_window_instance.isVisible():
            self.settings_window_instance.close()  # Settings usually don't have complex save prompts

        if self.display_window and self.display_window.isVisible():
            self.display_window.close()

        logger.info("Quitting application.")
        QCoreApplication.instance().quit()
        event.accept()