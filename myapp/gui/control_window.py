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
from ..utils.paths import get_icon_file_path  # Keep this
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

# ***** NEW IMPORTS *****
from ..audio.audio_program_manager import AudioProgramManager
from ..audio.audio_track_manager import AudioTrackManager
from ..audio.audio_player_manager import AudioPlayerManager

# ***** END NEW IMPORTS *****

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

        # ***** AUDIO PLAYER SETUP *****
        self.audio_program_manager = AudioProgramManager()
        self.audio_track_manager = AudioTrackManager()
        self.audio_player_manager = AudioPlayerManager(
            self.audio_program_manager,
            self.audio_track_manager,
            self  # Set parent for QObject lifecycle
        )
        self.audio_player_manager.program_playback_finished.connect(self._handle_audio_program_finished)
        self.audio_player_manager.playback_error_occurred.connect(self._handle_audio_playback_error)
        # Consider setting initial volume from settings
        # self.audio_player_manager.set_volume(self.settings_manager.get_setting("audio_volume", 0.8))
        # ***** END AUDIO PLAYER SETUP *****

        self.current_index = -1
        self.is_displaying = False  # Overall slide content (images/text)
        self._is_timer_for_initial_text_delay = False

        self.editor_window = None
        self.settings_window_instance = None

        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)

        self.text_controller.finished_and_should_advance_slide.connect(self._handle_text_finished_advance)

        self.indicator_icons = self._load_indicator_icons()
        self.setup_ui()  # UI setup depends on indicator_icons
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
            "audio": "audio_icon.png"  # ***** ADD AUDIO ICON *****
        }
        size = 16
        for name, filename in icon_files.items():
            try:
                path = get_icon_file_path(filename)
                if not path or not os.path.exists(path):
                    logger.warning(f"Indicator icon file not found: {filename}")
                    # Create a placeholder if icon not found for 'audio'
                    if name == "audio":
                        placeholder = QPixmap(size, size)
                        placeholder.fill(Qt.GlobalColor.transparent)  # Or some color
                        # You could draw a simple 'A' or music note if desired
                        icons[name] = placeholder
                        logger.info(f"Using placeholder for missing audio indicator icon: {filename}")
                    else:
                        icons[name] = QPixmap()
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
        self.playlist_view.setIconSize(get_thumbnail_size())  # This will use new size from thumbnail_generator
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

        # TODO: Future: Add a master audio play/pause button and volume slider here if desired.
        # For now, playback is automatic with slide.

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
            # ***** GET AUDIO PROGRAM INFO FOR THUMBNAIL *****
            audio_program_name = slide_data.get("audio_program_name")
            has_audio = bool(audio_program_name)
            # ***** END GET AUDIO PROGRAM INFO *****

            composite_icon = create_composite_thumbnail(
                slide_data,
                i,
                self.indicator_icons,
                has_text_overlay=has_text,
                has_audio_program=has_audio  # ***** PASS TO THUMBNAIL *****
            )
            item = QListWidgetItem(composite_icon, "")

            tooltip_parts = [f"Slide {i + 1}"]
            duration = slide_data.get("duration", 0)
            loop_target = slide_data.get("loop_to_slide", 0)

            # Refined tooltip logic
            primary_content_timed = False
            if has_text:
                tooltip_parts.append(f"Text: {text_overlay_info.get('paragraph_name', 'N/A')}")
                if text_overlay_info.get("sentence_timing_enabled"):
                    tooltip_parts.append("  Timed Sentences")
                    primary_content_timed = True  # Text timing dictates slide end unless slide duration is shorter
                if duration > 0:  # Duration is initial delay for text
                    tooltip_parts.append(f"  Initial Text Delay: {duration}s")
                    if not primary_content_timed: primary_content_timed = True  # Even manual text has a timed delay
                if text_overlay_info.get("auto_advance_slide"):
                    tooltip_parts.append("  Auto->Next Slide after text")

            if has_audio:
                tooltip_parts.append(f"Audio: {audio_program_name}")
                primary_content_timed = True  # Audio program implies timed content
                # If both text and audio, duration's meaning is more complex.
                # For now, just note its presence if > 0 and text wasn't using it as delay.
                if not has_text and duration > 0:
                    tooltip_parts.append(f"  Pre-Audio Delay: {duration}s")

            if not has_text and not has_audio:  # Neither text nor audio
                if duration > 0:
                    tooltip_parts.append(f"Plays for: {duration}s")
                    primary_content_timed = True
                else:
                    tooltip_parts.append("Manual advance")

            if loop_target > 0:
                # A loop is active if there's some timing mechanism (slide duration, text timing, or audio)
                if primary_content_timed or duration > 0:
                    tooltip_parts.append(f"Loops to: Slide {loop_target}")
                else:  # No explicit timing for the content itself
                    tooltip_parts.append(f"Loop to Slide {loop_target} (inactive - no duration/timed content)")

            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_view.addItem(item)

        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")
        issues = self.playlist_validator.validate(self.playlist)
        self.ui_updater.update_issue_display(issues)

    def _display_current_slide(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        # ***** STOP AUDIO PLAYER *****
        self.audio_player_manager.stop()
        # ***** END STOP AUDIO PLAYER *****
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

        can_show_text, initial_delay_for_text = self.text_controller.load_slide_text(slide_data)

        # ***** AUDIO PLAYBACK LOGIC *****
        audio_program_name = slide_data.get("audio_program_name")
        slide_duration_from_data = slide_data.get("duration", 0)  # This is the 'duration' field in JSON

        has_active_text_timing = can_show_text and self.text_controller._sentence_timing_enabled

        if audio_program_name:
            logger.info(f"Slide has audio program: '{audio_program_name}'. Loading and playing.")
            if self.audio_player_manager.load_program(audio_program_name):
                # If there's an initial delay (slide_duration_from_data) AND no timed text using that delay,
                # then this duration could be a pre-roll for the audio.
                if slide_duration_from_data > 0 and not can_show_text:  # Or if text is manual and duration is for audio pre-roll
                    logger.info(
                        f"Starting pre-audio delay of {slide_duration_from_data}s for slide {self.current_index + 1}.")
                    # Use slide_timer for this pre-audio delay. _handle_audio_program_finished will be connected to audio player.
                    self.slide_timer.start(slide_duration_from_data)
                    # Audio will be started by auto_advance_or_loop_slide when this timer fires if it's the only timed element.
                else:
                    self.audio_player_manager.play()
            else:
                logger.error(f"Failed to load audio program '{audio_program_name}' for slide {self.current_index + 1}.")
        # ***** END AUDIO PLAYBACK LOGIC *****

        # Determine slide timer based on content:
        # 1. If text is active and timed, text_controller handles its own timing.
        #    The 'duration' field in slide_data is the initial delay for text.
        # 2. If audio is active, it plays. If 'duration' field was a pre-roll, slide_timer handles that.
        #    If audio finishes, it might trigger slide advance via _handle_audio_program_finished.
        # 3. If only images with a duration, slide_timer handles that.

        if can_show_text:
            if initial_delay_for_text > 0:  # This is slide_data.duration
                logger.info(
                    f"Starting initial text delay of {initial_delay_for_text}s for slide {self.current_index + 1}.")
                self._is_timer_for_initial_text_delay = True
                self.slide_timer.start(initial_delay_for_text)
            else:
                logger.info("No initial text delay. Showing first sentence immediately.")
                self.text_controller.show_first_sentence()
        elif not audio_program_name and slide_duration_from_data > 0:  # No text, no audio, but has a duration for images
            logger.debug(
                f"Starting slide duration timer of {slide_duration_from_data}s for slide {self.current_index + 1} (images only).")
            self.slide_timer.start(slide_duration_from_data)

        # If audio is playing and there's no text or text is manual,
        # the audio's natural end (or loop) will be handled by audio_player_manager signals.
        # If slide_timer is also running (e.g. for a max duration if audio is very long and no loop),
        # that needs careful handling in auto_advance_or_loop_slide.

        self.ui_updater.update_all()

    def clear_display_screen(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        # ***** STOP AUDIO *****
        self.audio_player_manager.stop()
        # ***** END STOP AUDIO *****
        self._is_timer_for_initial_text_delay = False
        if self.display_window: self.display_window.clear_display()
        self.is_displaying = False
        self.ui_updater.update_all()

    def handle_show_clear_click(self):
        # This button's role might need to be re-evaluated with audio.
        # Is it "Show Slide / Clear Slide" or "Play Content / Stop Content"?
        # For now, keeping original logic but audio stops on clear.
        if self.is_displaying or self.text_controller.is_active() or self.audio_player_manager.is_active():
            self.clear_display_screen()
        else:
            slides = self.playlist.get_slides()
            if not slides: QMessageBox.information(self, "No Playlist", "Load a playlist..."); return
            if not (0 <= self.current_index < len(slides)): self._set_slide_index(0)
            self._display_current_slide()

    def next_slide(self):
        logger.debug("ControlWindow: next_slide called")
        # Stop current activities before moving
        self.slide_timer.stop()  # Stop slide timer first
        self.text_controller.stop_sentence_timer()
        self.audio_player_manager.stop()  # Stop audio

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
        self._display_current_slide()

    def prev_slide(self):
        logger.debug("ControlWindow: prev_slide called")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()
        self.audio_player_manager.stop()

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
        self._display_current_slide()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        logger.debug(
            f"List selection changed. Current: {current_item.data(Qt.ItemDataRole.UserRole) if current_item else 'None'}")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()
        # ***** STOP AUDIO ON SELECTION CHANGE *****
        self.audio_player_manager.stop()
        # ***** END STOP AUDIO *****

        if current_item:
            new_idx = current_item.data(Qt.ItemDataRole.UserRole)
            if self.current_index != new_idx:
                self.is_displaying = False
                self.text_controller.reset()
                if self.display_window: self.display_window.clearText()
            self._set_slide_index(new_idx)
        else:
            self._set_slide_index(-1)
            self.clear_display_screen()

    def auto_advance_or_loop_slide(self):
        logger.debug(f"Main SlideTimer timeout. For initial text delay: {self._is_timer_for_initial_text_delay}")

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: self.clear_display_screen(); return

        # Case 1: Timer was for initial text delay
        if self._is_timer_for_initial_text_delay:
            self._is_timer_for_initial_text_delay = False
            if self.text_controller.is_active():
                logger.info("Initial text delay timer expired. Showing first sentence.")
                self.text_controller.show_first_sentence()
            # If audio was also meant to start after this delay (and no timed text taking over)
            elif slide_data.get("audio_program_name") and not (
                    self.text_controller.is_active() and self.text_controller._sentence_timing_enabled):
                logger.info("Initial delay timer (for pre-audio) expired. Starting audio program.")
                self.audio_player_manager.play()  # Assumes it was loaded in _display_current_slide
            return

        # Case 2: Timer was for slide duration (images only, or pre-audio delay if audio is the only other content)
        audio_program_name = slide_data.get("audio_program_name")
        is_audio_active = self.audio_player_manager.is_active()  # is_playing or is_paused
        has_timed_text = self.text_controller.is_active() and self.text_controller._sentence_timing_enabled

        # If text is timed, it dictates its own advancement or signals slide end.
        # If audio is playing, it dictates its own advancement or signals slide end.
        # This timer is for slides that *don't* have self-advancing text or audio dictating the *entire* slide duration.
        if has_timed_text or (
                audio_program_name and is_audio_active):  # If audio IS the primary timer, this path shouldn't be hit for audio end
            logger.debug("SlideTimer fired, but timed text or active audio is managing slide. Ignoring here.")
            # If it was a pre-audio delay, and audio hasn't started, start it now.
            if audio_program_name and not is_audio_active and not has_timed_text:
                logger.info("SlideTimer (for pre-audio delay) expired. Starting audio program.")
                self.audio_player_manager.play()  # Assumes it was loaded
            return

        # If we reach here, the timer was for a simple image slide duration, or a max duration.
        self._process_slide_end_action(slide_data)

    def _handle_text_finished_advance(self):
        logger.info("TextController signaled to advance to next slide.")
        self.text_controller.reset()
        # If audio was playing alongside text and text finishes first, audio continues unless slide changes.
        # If slide changes, audio will be stopped by next_slide() or _display_current_slide().

        slides = self.playlist.get_slides()
        if self.current_index < len(slides) - 1:
            self._set_slide_index(self.current_index + 1)
            self._display_current_slide()
        else:
            logger.info("Text finished on the last slide, no next slide to auto-advance to.")
            # If audio is still playing on this last slide, let it continue.
            # If no audio, the slide remains (images shown), text cleared.
            if self.display_window: self.display_window.clearText()
            if not self.audio_player_manager.is_active():  # If no audio, truly end of slide activities
                self.is_displaying = True  # Keep images if any
                self.ui_updater.update_all()  # Reflect that text is done

    def _handle_audio_program_finished(self):
        logger.info(f"AudioPlayerManager signaled program finished for slide {self.current_index + 1}.")
        # This means the audio program (including its loops) has completed.
        # Now decide what to do with the slide itself.
        # If text is also on this slide and is manual, the slide stays.
        # If text was timed and finished earlier, or no text, then process slide end.
        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: return

        has_timed_text = self.text_controller.is_active() and self.text_controller._sentence_timing_enabled

        # If text is not timed or not active, then audio finishing means we process slide end actions (loop/next)
        if not has_timed_text:
            logger.info("Audio finished, and no active timed text. Processing slide end action.")
            self._process_slide_end_action(slide_data)
        else:
            logger.info(
                "Audio finished, but timed text is still active or was primary. Text controller will handle slide advance if configured.")
        self.ui_updater.update_all()

    def _process_slide_end_action(self, slide_data):
        """Handles looping or advancing after slide's main timed content (image duration, or audio) finishes."""
        if not slide_data: return

        logger.debug(f"Processing slide end action for slide {self.current_index + 1}")
        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)

        if loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                logger.info(f"Processing slide end: Looping to slide {loop_target_1_based}.")
                self._set_slide_index(loop_target_0_based)
                self._display_current_slide()
                return
            else:
                logger.warning(
                    f"Processing slide end: Invalid loop target ({loop_target_1_based}). Advancing if possible.")

        if self.current_index < num_slides - 1:
            logger.info("Processing slide end: Auto-advancing to next slide.")
            self.next_slide()  # This will call _display_current_slide after stopping current activities
        else:
            logger.info(
                "Processing slide end: Expired on last slide, no loop. Clearing display unless audio was the last thing.")
            self.clear_display_screen()

    def _handle_audio_playback_error(self, error_message):
        logger.error(f"Audio playback error received in ControlWindow: {error_message}")
        QMessageBox.warning(self, "Audio Playback Error", error_message)
        self.ui_updater.update_all()

    def closeEvent(self, event):
        logger.info("ControlWindow closeEvent triggered.")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()
        self.audio_player_manager.stop()

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

    def _load_and_update_playlist(self, file_path: str):
        self.audio_player_manager.stop()
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
        self.audio_player_manager.stop()
        if self.editor_window is None or not self.editor_window.isVisible():
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

    def _set_slide_index(self, new_index):  # Helper method, should exist or be added
        slides = self.playlist.get_slides()
        num_slides = len(slides)
        old_index = self.current_index
        changed = False

        if not slides:
            if self.current_index != -1: self.current_index = -1; changed = True
        elif 0 <= new_index < num_slides:
            if self.current_index != new_index: self.current_index = new_index; changed = True
        elif not (0 <= self.current_index < num_slides):
            self.current_index = 0 if slides else -1;
            changed = (old_index != self.current_index)

        if changed:
            logger.debug(f"Slide index changed from {old_index} to {self.current_index}")
            self.ui_updater.update_all()
        return changed

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):  # Helper, should exist or be added
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if self.current_index != index or not (
                    self.is_displaying or self.text_controller.is_active() or self.audio_player_manager.is_active()):
                if self._set_slide_index(index):
                    self._display_current_slide()
                elif self.current_index == index:  # re-selected same slide, ensure it displays
                    self._display_current_slide()