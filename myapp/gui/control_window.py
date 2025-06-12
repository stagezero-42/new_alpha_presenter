# myapp/gui/control_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QListWidget, QListWidgetItem, QHBoxLayout, QApplication,
    QListView, QAbstractItemView, QLabel, QFileDialog, QSlider
)
from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtMultimedia import QMediaPlayer

from .playlist_editor import PlaylistEditorWindow
from .settings_window import SettingsWindow
from .help_window import HelpWindow
from ..playlist.playlist import Playlist
from ..text.paragraph_manager import ParagraphManager
from ..utils.paths import get_icon_file_path, get_media_path
from ..settings.settings_manager import SettingsManager
from ..utils.schemas import DEFAULT_AUDIO_PROGRAM_VOLUME
from myapp.settings.key_bindings import setup_keybindings
from myapp import __version__
from .thumbnail_generator import create_composite_thumbnail, get_thumbnail_size, get_list_widget_height
from .slide_timer import SlideTimer
from .widget_helpers import create_button
from .playlist_validator import PlaylistValidator
from .text_controller import TextController
from .playlist_io_handler import PlaylistIOHandler
from .ui_updater import ControlWindowUIUpdater
from ..audio.audio_program_manager import AudioProgramManager
from ..audio.audio_track_manager import AudioTrackManager
from ..audio.slide_audio_player import SlideAudioPlayer
from ..audio.voice_over_player import VoiceOverPlayer

logger = logging.getLogger(__name__)


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        logger.debug("Initializing ControlWindow...")

        self.display_window = display_window
        if not self.display_window:
            raise ValueError("DisplayWindow instance must be provided.")

        self.setWindowTitle(f"Control Window v{__version__}")

        try:
            icon_name = "app_icon.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}")

        self.settings_manager = SettingsManager()
        self.playlist = Playlist()
        self.paragraph_manager = ParagraphManager()
        self.audio_program_manager = AudioProgramManager()
        self.audio_track_manager = AudioTrackManager()
        self.playlist_validator = PlaylistValidator(self.paragraph_manager)
        self.ui_updater = ControlWindowUIUpdater(self)

        self.display_window.video_duration_changed.connect(self._on_video_duration_changed)
        self.display_window.video_position_changed.connect(self._on_video_position_changed)
        self.display_window.video_state_changed.connect(self._handle_video_state_changed)

        self.slide_audio_player = SlideAudioPlayer(self.audio_program_manager, self.audio_track_manager, self)
        self.slide_audio_player.playback_error_occurred.connect(self._handle_slide_audio_error)

        self.voice_over_player = VoiceOverPlayer(self.audio_track_manager, self)
        self.voice_over_player.playback_error_occurred.connect(self._handle_voice_over_audio_error)

        self.text_controller = TextController(self.paragraph_manager, self.display_window, self.voice_over_player)
        self.playlist_io = PlaylistIOHandler(self, self.settings_manager)

        self.current_index = -1
        self.is_displaying = False
        self._is_timer_for_initial_text_delay = False
        self._is_timer_for_video_intro_delay = False

        self.editor_window = None
        self.settings_window_instance = None
        self.help_window_instance = None

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
            "slide": "slide_icon.png", "timer": "timer_icon.png", "loop": "loop_icon.png",
            "text": "text.png", "audio": "audio_icon.png", "video": "video.png"
        }
        size = 16
        for name, filename in icon_files.items():
            try:
                path = get_icon_file_path(filename)
                if not path or not os.path.exists(path):
                    logger.warning(f"Indicator icon file not found: {filename}")
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
        self.help_button = create_button("", "help.png", "Open Help", self.open_help_window)


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
        top_buttons_layout.addWidget(self.help_button)
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

        self.playlist_view.setStyleSheet("""
                  QListWidget::item:selected {
                      border-bottom: 4px solid #3399FF;
                      background: transparent;
                  }
                  QListWidget::item {
                      background: transparent;
                  }
              """)

        main_layout.addWidget(self.playlist_view)

        video_playback_layout = QHBoxLayout()
        self.video_play_pause_button = create_button("", "play.png", "Play/Pause Video", self._toggle_video_play_pause)
        self.video_progress_slider = QSlider(Qt.Horizontal)
        self.video_progress_slider.sliderMoved.connect(self.display_window.seek_video)
        self.video_time_label = QLabel("--:-- / --:--")
        video_playback_layout.addWidget(self.video_play_pause_button)
        video_playback_layout.addWidget(self.video_progress_slider)
        video_playback_layout.addWidget(self.video_time_label)
        main_layout.addLayout(video_playback_layout)

        playback_buttons_layout = QHBoxLayout()
        self.show_clear_button = QPushButton()
        self.show_clear_button.clicked.connect(self.handle_show_clear_click)

        #=================================

        self.show_clear_button.setStyleSheet("font-size: 15pt; padding: 12px;")

        self.toggle_display_button = create_button("Show Display", "show_display.png",
                                                   "Show or Hide the Display Window",
                                                   self.toggle_display_window_visibility)
        self.toggle_display_button.setStyleSheet("padding: 12px; font-size: 11pt;")
        self.toggle_display_button.setIconSize(QSize(24, 24))

        self.prev_button = create_button(" Prev", "previous.png", "Previous slide/sentence", self.prev_slide)
        self.prev_button.setStyleSheet("padding: 12px; font-size: 11pt;")
        self.prev_button.setIconSize(QSize(24, 24))

        self.next_button = create_button(" Next", "next.png", "Next slide/sentence", self.next_slide)
        self.next_button.setStyleSheet("padding: 12px; font-size: 11pt;")
        self.next_button.setIconSize(QSize(24, 24))

        #==================================

        playback_buttons_layout.addWidget(self.show_clear_button)
        playback_buttons_layout.addWidget(self.toggle_display_button)
        playback_buttons_layout.addStretch()
        playback_buttons_layout.addWidget(self.prev_button)
        playback_buttons_layout.addWidget(self.next_button)
        main_layout.addLayout(playback_buttons_layout)

        self.setCentralWidget(central_widget)
        self.resize(700, 295)
        logger.debug("ControlWindow UI setup complete.")
        self.ui_updater.update_issue_display([])

    # ... (rest of the file is unchanged, but included for completeness) ...
    def populate_playlist_view(self):
        logger.debug("Populating playlist view...")
        self.playlist_view.clear()
        for i, slide_data in enumerate(self.playlist.get_slides()):
            text_overlay_info = slide_data.get("text_overlay", {})
            has_text = bool(text_overlay_info and text_overlay_info.get("paragraph_name"))
            audio_config = {"audio_program_name": slide_data.get("audio_program_name"),
                            "loop_audio_program": slide_data.get("loop_audio_program", False)}
            has_audio = bool(audio_config["audio_program_name"])
            composite_icon = create_composite_thumbnail(slide_data, i, self.indicator_icons, has_text_overlay=has_text,
                                                        has_audio_program=has_audio,
                                                        audio_program_loops=audio_config["loop_audio_program"])
            item = QListWidgetItem(composite_icon, "")
            is_video = bool(slide_data.get("video_path"))
            tooltip_parts = [f"Slide {i + 1}"]
            if is_video:
                tooltip_parts.append(f"Video: {os.path.basename(slide_data['video_path'])}")
            tooltip_parts.append(f"Layers: {len(slide_data.get('layers', []))}")
            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_view.addItem(item)
        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")
        issues = self.playlist_validator.validate(self.playlist)
        self.ui_updater.update_issue_display(issues)

    def _handle_video_state_changed(self, state: QMediaPlayer.PlaybackState):
        self.ui_updater.update_video_button_icon()
        if state == QMediaPlayer.PlaybackState.StoppedState and self.display_window.current_video_path:
            slide_data = self.playlist.get_slide(self.current_index)
            if not slide_data: return
            auto_advance = slide_data.get("video_auto_advance", True)
            if not auto_advance:
                logger.info("Video finished, but auto-advance is disabled for this slide.")
                return
            logger.debug("Video playback stopped. Checking for outro/loop.")
            outro_delay = slide_data.get("duration", 0)
            if outro_delay > 0:
                self._is_timer_for_video_intro_delay = False
                self._is_timer_for_initial_text_delay = False
                self.slide_timer.start(outro_delay / 1000.0)
            else:
                self.auto_advance_or_loop_slide()

    def _display_current_slide(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        self.slide_audio_player.stop()
        self._is_timer_for_initial_text_delay = False
        self._is_timer_for_video_intro_delay = False

        slides = self.playlist.get_slides()
        if not (0 <= self.current_index < len(slides)):
            self.clear_display_screen()
            return

        logger.info(f"Displaying slide {self.current_index + 1}.")
        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data:
            logger.warning(f"Slide data is None for index {self.current_index}, clearing.")
            self.clear_display_screen()
            return

        self.is_displaying = True
        self.display_window.display_slide(slide_data)

        is_video_slide = bool(slide_data.get("video_path"))

        if is_video_slide:
            if slide_data.get("video_autoplay", True):
                intro_delay = slide_data.get("video_intro_delay_ms", 0)
                if intro_delay > 0:
                    logger.info(f"Starting video intro delay: {intro_delay}ms")
                    self._is_timer_for_video_intro_delay = True
                    self.slide_timer.start(intro_delay / 1000.0)
                else:
                    self.display_window.play_video()
        else:
            audio_config_to_pass = {"audio_program_name": slide_data.get("audio_program_name"),
                                    "loop_audio_program": slide_data.get("loop_audio_program", False),
                                    "audio_intro_delay_ms": slide_data.get("audio_intro_delay_ms", 0),
                                    "audio_outro_duration_ms": slide_data.get("audio_outro_duration_ms", 0),
                                    "audio_program_volume": slide_data.get("audio_program_volume",
                                                                           DEFAULT_AUDIO_PROGRAM_VOLUME)}
            if audio_config_to_pass["audio_program_name"]:
                self.slide_audio_player.load_program_and_play(audio_config_to_pass)

            can_show_text, initial_delay_for_text = self.text_controller.load_slide_text(slide_data)
            if can_show_text:
                if initial_delay_for_text > 0:
                    self._is_timer_for_initial_text_delay = True
                    self.slide_timer.start(initial_delay_for_text)
                else:
                    self.text_controller.show_first_sentence()
            else: # If there is no text overlay
                slide_duration = slide_data.get("duration", 0)
                if slide_duration > 0:
                    # This will now start the timer for slides with audio but no text,
                    # or slides with neither audio nor text.
                    self.slide_timer.start(slide_duration)

        self.ui_updater.update_all()

    def _on_video_position_changed(self, position):
        if not self.video_progress_slider.isSliderDown():
            self.video_progress_slider.setValue(position)
        self.ui_updater.update_video_time_label(position, self.display_window.media_player.duration())

    def _toggle_video_play_pause(self):
        if self.display_window.get_playback_state() == QMediaPlayer.PlaybackState.PlayingState:
            self.display_window.pause_video()
        else:
            self.display_window.play_video()

    def _on_video_duration_changed(self, duration):
        self.video_progress_slider.setRange(0, duration)
        self.ui_updater.update_video_time_label(self.display_window.media_player.position(), duration)

    def _handle_slide_audio_error(self, error_message: str):
        logger.error(f"SlideAudioPlayer reported error: {error_message}")
        QMessageBox.warning(self, "Slide Audio Playback Error", error_message)

    def _handle_voice_over_audio_error(self, error_message: str):
        logger.error(f"VoiceOverPlayer reported error: {error_message}")
        QMessageBox.warning(self, "Voice-Over Audio Playback Error", error_message)

    def clear_display_screen(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        self.slide_audio_player.stop()
        self._is_timer_for_initial_text_delay = False
        self._is_timer_for_video_intro_delay = False
        if self.display_window: self.display_window.clear_display()
        self.is_displaying = False
        self.ui_updater.update_all()

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
            self.current_index = -1 if not slides else 0
            changed = (old_index != self.current_index)
        if changed: self.ui_updater.update_all()
        return changed

    def handle_show_clear_click(self):
        if self.is_displaying or self.text_controller.is_active() or self.slide_audio_player.is_audio_active() or (
                self.display_window and self.display_window.current_video_path):
            self.clear_display_screen()
        else:
            slides = self.playlist.get_slides()
            if not slides: QMessageBox.information(self, "No Playlist", "Load a playlist..."); return
            if not (0 <= self.current_index < len(slides)): self._set_slide_index(0)
            self._display_current_slide()

    def next_slide(self):
        logger.debug("ControlWindow: next_slide called")
        self.slide_timer.stop()
        if self.text_controller.is_active():
            if self.text_controller.show_next_sentence():
                self.ui_updater.update_all();
                return
        slides = self.playlist.get_slides()
        if not slides or not (self.current_index < len(slides) - 1):
            logger.info("Cannot go next: No more slides or playlist empty.")
            self.ui_updater.update_all()
            return
        self._set_slide_index(self.current_index + 1)
        self._display_current_slide()

    def prev_slide(self):
        logger.debug("ControlWindow: prev_slide called")
        self.slide_timer.stop()
        if self.text_controller.is_active():
            if self.text_controller.show_prev_sentence():
                self.ui_updater.update_all();
                return
        if not self.playlist.get_slides() or self.current_index <= 0:
            logger.info("Cannot go previous: No slides or already at the start.")
            self.ui_updater.update_all()
            return
        self._set_slide_index(self.current_index - 1)
        self._display_current_slide()

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            is_something_active = self.is_displaying or self.text_controller.is_active() or self.slide_audio_player.is_audio_active() or (
                        self.display_window and self.display_window.current_video_path)
            if self.current_index != index or not is_something_active:
                if self._set_slide_index(index): self._display_current_slide()
            elif self.current_index == index and not is_something_active:
                self._display_current_slide()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        logger.debug(
            f"List selection changed. Current: {current_item.data(Qt.ItemDataRole.UserRole) if current_item else 'None'}")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()
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
        logger.debug(f"Main SlideTimer timeout.")
        if self._is_timer_for_video_intro_delay:
            self._is_timer_for_video_intro_delay = False
            logger.info("Video intro timer expired. Playing video.")
            self.display_window.play_video()
            return
        if self._is_timer_for_initial_text_delay:
            self._is_timer_for_initial_text_delay = False
            if self.text_controller.is_active():
                logger.info("Initial text delay timer expired. Showing first sentence.")
                self.text_controller.show_first_sentence()
            else:
                logger.warning("Initial text delay timer expired, but no text active.")
            return
        if not self.is_displaying:
            logger.warning("Slide duration/outro timer fired but main display is false. Stopping.")
            return
        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: self.clear_display_screen(); return
        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)
        if loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                logger.info(f"Slide timer: Looping slide to {loop_target_1_based}.")
                self._set_slide_index(loop_target_0_based)
                self._display_current_slide()
                return
        if self.current_index < num_slides - 1:
            logger.info("Slide timer: Auto-advancing to next slide.")
            self.next_slide()
        else:
            logger.info("Slide timer: Expired on last slide, no valid loop. Clearing display.")
            self.clear_display_screen()

    def _handle_text_finished_advance(self):
        logger.info("TextController signaled to advance to next slide.")
        self.text_controller.reset()
        slides = self.playlist.get_slides()
        if self.current_index < len(slides) - 1:
            self._set_slide_index(self.current_index + 1)
            self._display_current_slide()
        else:
            logger.info("Text finished on last slide, no next slide to advance to.")
            self.is_displaying = True
            if self.display_window: self.display_window.clearText()
        self.ui_updater.update_all()

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
            logger.info("No valid last playlist found.")
            self.populate_playlist_view()
            self.clear_display_screen()
            self.ui_updater.update_all()

    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            self.slide_audio_player.stop()
            self.voice_over_player.stop()
            if self.display_window.get_playback_state() != QMediaPlayer.PlaybackState.StoppedState:
                self.display_window.stop_video()
            self.editor_window = PlaylistEditorWindow(self.display_window, self.playlist, self)
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        logger.info(f"Playlist saved by editor, reloading: {saved_playlist_path}")
        self._load_and_update_playlist(saved_playlist_path)

    def open_settings_window(self):
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            self.settings_window_instance = SettingsWindow(self)
            self.settings_window_instance.show()
        else:
            self.settings_window_instance.activateWindow()
            self.settings_window_instance.raise_()

    def open_help_window(self):
        if self.help_window_instance is None or not self.help_window_instance.isVisible():
            # Pass the anchor for the "Control Window" section
            self.help_window_instance = HelpWindow(self, anchor="control_window")
            self.help_window_instance.show()
        else:
            self.help_window_instance.activateWindow()
            self.help_window_instance.raise_()

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
        self.text_controller.reset()
        self.slide_audio_player.stop()
        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close(): logger.info("Playlist editor close cancelled."); event.ignore(); return
        if self.settings_window_instance and self.settings_window_instance.isVisible(): self.settings_window_instance.close()
        if self.display_window and self.display_window.isVisible(): self.display_window.close()
        logger.info("Quitting application.")
        QCoreApplication.instance().quit()
        event.accept()