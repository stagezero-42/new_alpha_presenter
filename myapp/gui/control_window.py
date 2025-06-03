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

from .playlist_editor import PlaylistEditorWindow
from .settings_window import SettingsWindow
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
# --- NEW IMPORTS ---
from ..audio.audio_program_manager import AudioProgramManager
from ..audio.audio_track_manager import AudioTrackManager
from ..audio.slide_audio_player import SlideAudioPlayer

# --- END NEW IMPORTS ---

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

        # --- NEW AUDIO COMPONENTS ---
        self.audio_program_manager = AudioProgramManager()
        self.audio_track_manager = AudioTrackManager()
        self.slide_audio_player = SlideAudioPlayer(self.audio_program_manager, self.audio_track_manager, self)
        self.slide_audio_player.playback_error_occurred.connect(self._handle_slide_audio_error)
        # --- END NEW AUDIO COMPONENTS ---

        self.current_index = -1
        self.is_displaying = False
        self._is_timer_for_initial_text_delay = False

        self.editor_window = None
        self.settings_window_instance = None

        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)
        self.text_controller.finished_and_should_advance_slide.connect(self._handle_text_finished_advance)

        self.indicator_icons = self._load_indicator_icons()
        self.setup_ui()
        setup_keybindings(self, self.settings_manager)
        self.ui_updater.update_all()
        self.load_last_playlist()
        logger.debug("ControlWindow initialization complete.")

    def _load_indicator_icons(self):
        logger.debug("Loading indicator icons...")
        icons = {}
        icon_files = {
            "slide": "slide_icon.png",
            "timer": "timer_icon.png",
            "loop": "loop_icon.png",
            "text": "text.png",
            "audio": "audio_icon.png"  # --- NEW AUDIO ICON ---
        }
        size = 16
        for name, filename in icon_files.items():
            try:
                path = get_icon_file_path(filename)
                if not path or not os.path.exists(path):
                    logger.warning(f"Indicator icon file not found: {filename}")
                    icons[name] = QPixmap();
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

    # ... (setup_ui remains mostly the same, ensure buttons are connected) ...
    def setup_ui(self):
        logger.debug("Setting up ControlWindow UI...")
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        top_buttons_layout = QHBoxLayout()
        self.load_button = create_button(" Load Playlist", "load.png", "Load a playlist (Ctrl+L)",
                                         self.load_playlist_dialog)
        self.edit_playlist_button = create_button(" Edit Playlist", "edit.png", "Open the Playlist Editor (Ctrl+E)",
                                                  self.open_playlist_editor)
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
        self.resize(700, 350)
        logger.debug("ControlWindow UI setup complete.")
        self.ui_updater.update_issue_display([])

    def populate_playlist_view(self):
        logger.debug("Populating playlist view...")
        self.playlist_view.clear()

        for i, slide_data in enumerate(self.playlist.get_slides()):
            text_overlay_info = slide_data.get("text_overlay")
            if not isinstance(text_overlay_info, dict): text_overlay_info = {}
            has_text = bool(text_overlay_info.get("paragraph_name"))
            # --- NEW: Check for audio ---
            has_audio = bool(slide_data.get("audio_program_name"))
            audio_loops = slide_data.get("loop_audio_program", False)
            # --- END NEW ---

            composite_icon = create_composite_thumbnail(
                slide_data, i, self.indicator_icons,
                has_text_overlay=has_text,
                has_audio_program=has_audio,  # Pass to thumbnail generator
                audio_program_loops=audio_loops  # Pass to thumbnail generator
            )
            item = QListWidgetItem(composite_icon, "")

            # Tooltip generation (simplified for brevity, ensure it includes audio info)
            tooltip_parts = [f"Slide {i + 1}"]
            duration = slide_data.get("duration", 0)
            loop_target = slide_data.get("loop_to_slide", 0)  # Slide loop

            if has_audio:
                audio_desc = f"Audio: {slide_data.get('audio_program_name')}"
                if audio_loops: audio_desc += " (Loop)"
                tooltip_parts.append(audio_desc)

            if has_text:
                text_desc = f"Text: {text_overlay_info.get('paragraph_name', 'N/A')}"
                if text_overlay_info.get("sentence_timing_enabled"): text_desc += " (Timed)"
                if duration > 0: text_desc += f", Initial Delay: {duration}s"
                tooltip_parts.append(text_desc)
            elif not has_audio and duration > 0:  # No text, no audio, but has duration
                tooltip_parts.append(f"Slide Duration: {duration}s")
            elif not has_audio and not has_text:  # No text, no audio, no duration
                tooltip_parts.append("Manual Advance")

            if loop_target > 0:  # Slide loop
                is_slide_timed_for_loop = duration > 0 or (
                            has_text and text_overlay_info.get("sentence_timing_enabled"))
                if is_slide_timed_for_loop:
                    tooltip_parts.append(f"Loops Slide to S{loop_target}")
                else:
                    tooltip_parts.append(f"Loops Slide to S{loop_target} (Inactive)")

            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_view.addItem(item)

        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")
        issues = self.playlist_validator.validate(self.playlist)
        self.ui_updater.update_issue_display(issues)

    def _handle_slide_audio_error(self, error_message: str):
        logger.error(f"SlideAudioPlayer reported error: {error_message}")
        QMessageBox.warning(self, "Audio Playback Error", error_message)
        # Potentially update UI to show audio playback failed for the current slide

    def _display_current_slide(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        self.slide_audio_player.stop()  # --- STOP PREVIOUS AUDIO ---
        self._is_timer_for_initial_text_delay = False

        slides = self.playlist.get_slides()
        if not (0 <= self.current_index < len(slides)):
            self.clear_display_screen();
            return

        logger.info(f"Displaying slide {self.current_index + 1}.")
        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data:
            logger.warning(f"Slide data is None for valid index {self.current_index}, clearing.")
            self.clear_display_screen();
            return

        self.is_displaying = True
        self.display_window.display_images(slide_data.get("layers", []))

        # --- NEW AUDIO PLAYBACK ---
        audio_program_name = slide_data.get("audio_program_name")
        loop_audio = slide_data.get("loop_audio_program", False)
        if audio_program_name:
            logger.info(f"Slide {self.current_index + 1} has audio program: '{audio_program_name}', Loop: {loop_audio}")
            self.slide_audio_player.load_program_and_play(audio_program_name, loop_audio)
        # --- END NEW AUDIO PLAYBACK ---

        can_show_text, initial_delay_for_text = self.text_controller.load_slide_text(slide_data)
        if can_show_text:
            # Audio plays independently. Text delay/timing is separate.
            # The slide's "duration" field is now primarily for initial text delay if text exists,
            # or for slide advance if no text and no audio.
            # If audio exists, it dictates its own "duration" or loops. Slide duration for auto-advance
            # in presence of audio needs careful consideration (e.g. does slide timer cut audio, or wait for audio?)
            # For now, audio plays, text starts after its delay.
            if initial_delay_for_text > 0:
                logger.info(
                    f"Starting initial text delay of {initial_delay_for_text}s for slide {self.current_index + 1}.")
                self._is_timer_for_initial_text_delay = True
                self.slide_timer.start(initial_delay_for_text)
            else:
                logger.info("No initial text delay. Showing first sentence immediately.")
                self.text_controller.show_first_sentence()
        elif not audio_program_name:  # No text and no audio, use slide duration for advance
            slide_duration_no_text_no_audio = slide_data.get("duration", 0)
            if slide_duration_no_text_no_audio > 0:
                logger.debug(
                    f"Starting slide duration timer of {slide_duration_no_text_no_audio}s for slide {self.current_index + 1} (no text, no audio).")
                self.slide_timer.start(slide_duration_no_text_no_audio)

        # If there's audio but no text, and slide duration > 0, what happens?
        # Current: Audio plays. If slide_duration is also set, slide_timer will fire.
        # This could mean slide advances while audio is still playing if audio is longer.
        # This matches "audio plays independently".

        self.ui_updater.update_all()

    def clear_display_screen(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        self.slide_audio_player.stop()  # --- STOP AUDIO ---
        self._is_timer_for_initial_text_delay = False
        if self.display_window: self.display_window.clear_display()
        self.is_displaying = False
        self.ui_updater.update_all()

    # Methods like next_slide, prev_slide, handle_list_selection, auto_advance_or_loop_slide,
    # _load_and_update_playlist, load_playlist_dialog, load_last_playlist,
    # open_playlist_editor, handle_playlist_saved_by_editor, open_settings_window,
    # toggle_display_window_visibility, close_application, closeEvent
    # need to ensure self.slide_audio_player.stop() is called when appropriate
    # (e.g., when changing slides or clearing the display).
    # This is already done in clear_display_screen and _display_current_slide (at the start).
    # For next_slide/prev_slide, _display_current_slide is called which handles stopping previous audio.

    def _handle_text_finished_advance(self):
        logger.info("TextController signaled to advance to next slide.")
        # Audio is independent, so it keeps playing unless the slide itself changes.
        # We only stop text controller here.
        self.text_controller.reset()

        slides = self.playlist.get_slides()
        if self.current_index < len(slides) - 1:
            self._set_slide_index(self.current_index + 1)
            self._display_current_slide()  # This will handle audio for the new slide
        else:
            logger.info("Text finished on the last slide, no next slide to auto-advance to.")
            self.is_displaying = True
            if self.display_window: self.display_window.clearText()
            # Audio might still be playing if it's longer than text or looping
        self.ui_updater.update_all()

    # ... (other methods like _set_slide_index, handle_show_clear_click, next_slide, prev_slide, etc. remain,
    # ensuring that _display_current_slide and clear_display_screen correctly manage audio start/stop)
    def _set_slide_index(self, new_index):
        slides = self.playlist.get_slides()
        num_slides = len(slides)
        old_index = self.current_index
        changed = False

        if not slides:
            if self.current_index != -1: self.current_index = -1; changed = True
        elif 0 <= new_index < num_slides:
            if self.current_index != new_index: self.current_index = new_index; changed = True
        elif not (0 <= self.current_index < num_slides):
            self.current_index = -1 if not slides else 0;
            changed = (old_index != self.current_index)

        if changed:
            self.ui_updater.update_all()
        return changed

    def handle_show_clear_click(self):
        if self.is_displaying or self.text_controller.is_active() or self.slide_audio_player.is_playing:
            self.clear_display_screen()
        else:
            slides = self.playlist.get_slides()
            if not slides: QMessageBox.information(self, "No Playlist", "Load a playlist..."); return
            if not (0 <= self.current_index < len(slides)): self._set_slide_index(0)
            self._display_current_slide()

    def next_slide(self):
        logger.debug("ControlWindow: next_slide called")
        self.text_controller.stop_sentence_timer()

        if self.text_controller.is_active():
            if self.text_controller.show_next_sentence():
                self.ui_updater.update_all();
                return
            else:
                self.text_controller.reset()

        slides = self.playlist.get_slides()
        if not slides or not (self.current_index < len(slides) - 1):
            logger.info("Cannot go next: No more slides or playlist empty.")
            self.ui_updater.update_all();
            return

        self._set_slide_index(self.current_index + 1)
        self._display_current_slide()  # This will stop previous audio and start new if any

    def prev_slide(self):
        logger.debug("ControlWindow: prev_slide called")
        self.text_controller.stop_sentence_timer()

        if self.text_controller.is_active():
            if self.text_controller.show_prev_sentence():
                self.ui_updater.update_all();
                return
            else:
                self.text_controller.reset()

        if not self.playlist.get_slides() or self.current_index <= 0:
            logger.info("Cannot go previous: No slides or already at the start.")
            self.ui_updater.update_all();
            return

        self._set_slide_index(self.current_index - 1)
        self._display_current_slide()  # This will stop previous audio and start new if any

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if self.current_index != index or not (
                    self.is_displaying or self.text_controller.is_active() or self.slide_audio_player.is_playing):
                if self._set_slide_index(index):
                    self._display_current_slide()
            elif self.current_index == index:
                self._display_current_slide()  # Re-trigger display to ensure audio restarts if cleared previously

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        logger.debug(
            f"List selection changed. Current: {current_item.data(Qt.ItemDataRole.UserRole) if current_item else 'None'}")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()
        # Do not stop audio here on mere selection change, only when a new slide is actually displayed or cleared.
        # self.slide_audio_player.stop() # Moved to _display_current_slide / clear_display_screen

        if current_item:
            new_idx = current_item.data(Qt.ItemDataRole.UserRole)
            if self.current_index != new_idx:
                # Mark that current display (images, text, audio) is no longer valid for the *new* selection
                # until "Show" is clicked or slide is auto-played.
                # We don't clear_display_screen() here, as that would interrupt audio if user is just clicking around
                # without intending to change what's actively playing *yet*.
                # The actual change of displayed content (and audio) happens on _display_current_slide.
                self.is_displaying = False  # Visuals are stale for this new selection until shown
                self.text_controller.reset()  # Text is stale
                if self.display_window: self.display_window.clearText()  # Clear just text for now
            self._set_slide_index(new_idx)
        else:
            self._set_slide_index(-1)
            self.clear_display_screen()

    def auto_advance_or_loop_slide(self):
        logger.debug(f"Main SlideTimer timeout. For initial text delay: {self._is_timer_for_initial_text_delay}")

        if self._is_timer_for_initial_text_delay:
            self._is_timer_for_initial_text_delay = False
            if self.text_controller.is_active():
                logger.info("Initial text delay timer expired. Showing first sentence.")
                self.text_controller.show_first_sentence()
            else:
                logger.warning("Initial text delay timer expired, but no text active.")
            return  # Audio is independent and continues playing

        # If timer was for slide duration (no text, or text finished and didn't auto-advance slide)
        # Audio plays independently. If slide advances, audio for current slide stops.
        if not self.is_displaying:
            logger.warning("Slide duration timer fired but main display (is_displaying) is false. Stopping.");
            return

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: self.clear_display_screen(); return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)  # This is slide loop, not audio loop

        if loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                logger.info(f"Slide timer: Looping slide to {loop_target_1_based}.")
                self._set_slide_index(loop_target_0_based)
                self._display_current_slide();
                return  # This will restart audio for the target slide
            else:
                logger.warning(
                    f"Slide timer: Invalid slide loop target ({loop_target_1_based}). Advancing if possible.")

        if self.current_index < num_slides - 1:
            logger.info("Slide timer: Auto-advancing to next slide.")
            self.next_slide()  # This will call _display_current_slide, stopping current audio, starting next
        else:
            logger.info("Slide timer: Expired on last slide, no slide loop. Clearing display (and audio).")
            self.clear_display_screen()

    def _load_and_update_playlist(self, file_path: str):
        self.clear_display_screen()
        try:
            self.playlist.load(file_path)
            self.settings_manager.set_current_playlist(file_path)
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist()
            self.settings_manager.set_current_playlist(None)

        self.populate_playlist_view()
        self._set_slide_index(0 if self.playlist.get_slides() else -1)
        self.ui_updater.update_all()

    def load_playlist_dialog(self):
        file_path = self.playlist_io.prompt_load_playlist()
        if file_path: self._load_and_update_playlist(file_path)

    def load_last_playlist(self):
        file_path = self.playlist_io.get_last_playlist_path()
        if file_path:
            logger.info(f"Attempting to load last playlist: {file_path}")
            self._load_and_update_playlist(file_path)
        else:
            logger.info("No valid last playlist found. Starting with empty setup.")
            self.populate_playlist_view()
            self.clear_display_screen()
            self.ui_updater.update_all()

    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            # Stop slide-specific audio when opening editor, as editor might play its own previews
            self.slide_audio_player.stop()
            self.editor_window = PlaylistEditorWindow(self.display_window, self.playlist, self)
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow();
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
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
                screens = QApplication.instance().screens()
                if screens:
                    target_screen = screens[1] if len(screens) > 1 else screens[0]
                    self.display_window.setGeometry(target_screen.geometry())
                self.display_window.showFullScreen()
                self.toggle_display_button.setText("Hide Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("hide_display.png")))

    def close_application(self):
        self.close()

    def closeEvent(self, event):
        logger.info("ControlWindow closeEvent triggered.")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()
        self.slide_audio_player.stop()  # --- STOP AUDIO ON CLOSE ---

        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close():
                logger.info("Playlist editor close cancelled, aborting ControlWindow close.")
                event.ignore();
                return

        if self.settings_window_instance and self.settings_window_instance.isVisible():
            self.settings_window_instance.close()

        if self.display_window and self.display_window.isVisible():
            self.display_window.close()

        logger.info("Quitting application.")
        QCoreApplication.instance().quit()
        event.accept()