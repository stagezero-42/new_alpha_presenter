# myapp/gui/sentence_vo_player_panel.py
import os
import logging
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_media_file_path, get_icon_file_path
from .widget_helpers import create_button
from ..utils.schemas import DEFAULT_VOICE_OVER_VOLUME

logger = logging.getLogger(__name__)


class SentenceVOPlayerPanel(QGroupBox):
    playback_error_occurred = Signal(str)
    duration_ready = Signal(bool)

    def __init__(self, track_manager: AudioTrackManager, parent=None):
        super().__init__("Voice-Over Playback", parent)
        self.track_manager = track_manager

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(DEFAULT_VOICE_OVER_VOLUME)

        self.current_loaded_track_meta_name = None
        self.current_track_duration_ms_from_player = 0

        self._setup_ui()
        self._connect_signals()
        self.update_controls_state()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.loaded_track_label = QLabel("Loaded for Playback: None")
        layout.addWidget(self.loaded_track_label)
        self.playback_slider = QSlider(Qt.Orientation.Horizontal)
        self.playback_slider.setRange(0, 1000)
        layout.addWidget(self.playback_slider)
        time_layout = QHBoxLayout()
        self.current_pos_label = QLabel("00:00.000")
        self.total_duration_label = QLabel("/ 00:00.000")
        time_layout.addWidget(self.current_pos_label)
        time_layout.addStretch()
        time_layout.addWidget(self.total_duration_label)
        layout.addLayout(time_layout)
        controls_layout = QHBoxLayout()
        self.play_button = create_button("", "play.png", "Play/Pause", self._toggle_play_pause)
        self.stop_button = create_button("", "stop.png", "Stop", self._stop_playback)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

    def _connect_signals(self):
        self.playback_slider.sliderMoved.connect(self.media_player.setPosition)
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)
        self.media_player.mediaStatusChanged.connect(self._on_player_media_status_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)
        self.media_player.playbackStateChanged.connect(self._update_player_button_icon)

    def load_vo_track(self, track_meta_name: str | None):
        logger.debug(f"SentenceVOPlayerPanel: Load track requested: '{track_meta_name}'")
        self._stop_playback(internal_call=True)

        was_duration_valid_before_load = self.current_track_duration_ms_from_player > 0

        self.current_loaded_track_meta_name = None
        self.current_track_duration_ms_from_player = 0
        self._reset_ui_for_new_track()

        if not track_meta_name:
            self.loaded_track_label.setText("No V/O track selected.")
            self.update_controls_state()
            if was_duration_valid_before_load:
                self.duration_ready.emit(False)
            return

        self.current_loaded_track_meta_name = track_meta_name
        try:
            track_metadata = self.track_manager.load_track_metadata(track_meta_name)
            if not track_metadata or not track_metadata.get("file_path"):
                self.loaded_track_label.setText(f"Error: Metadata missing for {track_meta_name}")
                self.current_loaded_track_meta_name = None
                if was_duration_valid_before_load: self.duration_ready.emit(False)
                self.update_controls_state()
                return

            media_file_name = track_metadata["file_path"]
            media_content_path = get_media_file_path(media_file_name)

            if os.path.exists(media_content_path):
                self.loaded_track_label.setText(f"Loading: {track_meta_name}...")
                self.media_player.setSource(QUrl.fromLocalFile(media_content_path))
            else:
                self.loaded_track_label.setText(f"Error: File not found - {media_file_name}")
                self.current_loaded_track_meta_name = None
                if was_duration_valid_before_load: self.duration_ready.emit(False)
        except Exception as e:
            logger.error(f"Exception loading V/O track '{track_meta_name}': {e}", exc_info=True)
            self.loaded_track_label.setText(f"Error loading: {track_meta_name}")
            self.current_loaded_track_meta_name = None
            if was_duration_valid_before_load: self.duration_ready.emit(False)

        self.update_controls_state()

    def _reset_ui_for_new_track(self):
        self.loaded_track_label.setText("Loaded for Playback: None")
        self.playback_slider.setValue(0)
        self.current_pos_label.setText(self._format_ms_time(0))
        self.total_duration_label.setText(f"/ {self._format_ms_time(0)}")
        self._update_player_button_icon()

        if self.current_track_duration_ms_from_player > 0:
            self.duration_ready.emit(False)
        self.current_track_duration_ms_from_player = 0

    def _on_player_position_changed(self, position_ms):
        if not self.playback_slider.isSliderDown():
            self.playback_slider.setValue(position_ms)
        self.current_pos_label.setText(self._format_ms_time(position_ms))

    def _on_player_duration_changed(self, duration_ms):
        logger.debug(f"SentenceVOPlayerPanel: Player duration changed: {duration_ms} ms")

        was_duration_valid = self.current_track_duration_ms_from_player > 0

        self.current_track_duration_ms_from_player = duration_ms if duration_ms > 0 else 0
        self.playback_slider.setRange(0,
                                      self.current_track_duration_ms_from_player if self.current_track_duration_ms_from_player > 0 else 1000)
        self.total_duration_label.setText(f"/ {self._format_ms_time(self.current_track_duration_ms_from_player)}")
        self.update_controls_state()

        is_duration_now_valid = self.current_track_duration_ms_from_player > 0
        if was_duration_valid != is_duration_now_valid:
            self.duration_ready.emit(is_duration_now_valid)

    def _on_player_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        track_name = self.current_loaded_track_meta_name or "N/A"
        logger.info(f"SentenceVOPlayerPanel: MediaStatusChanged for '{track_name}': {status}")

        is_now_invalid = False
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.loaded_track_label.setText(f"Ready: {track_name}")
            self.media_player.stop()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._update_player_button_icon()
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            self._reset_ui_for_new_track()
            is_now_invalid = True
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.error(f"InvalidMedia status for V/O track '{track_name}'")
            self.loaded_track_label.setText(f"Error: Invalid media for {track_name}")
            self.current_loaded_track_meta_name = None
            is_now_invalid = True
        elif status == QMediaPlayer.MediaStatus.LoadingMedia:
            self.loaded_track_label.setText(f"Loading: {track_name}...")

        if is_now_invalid and self.current_track_duration_ms_from_player > 0:
            self.current_track_duration_ms_from_player = 0
            self.duration_ready.emit(False)
        self.update_controls_state()

    def _on_player_error(self, error_enum, error_string=""):
        detailed_error_string = self.media_player.errorString()
        final_error_message = detailed_error_string if detailed_error_string else error_string
        track_name = self.current_loaded_track_meta_name or 'Unknown'
        logger.error(
            f"SentenceVOPlayerPanel: Error for track '{track_name}': {final_error_message} (Enum: {error_enum})")
        self.playback_error_occurred.emit(f"Playback error on '{track_name}': {final_error_message}")
        self.loaded_track_label.setText(f"Playback Error: {track_name}")

        if self.current_track_duration_ms_from_player > 0:
            self.duration_ready.emit(False)
        self.current_loaded_track_meta_name = None
        self.current_track_duration_ms_from_player = 0
        self.update_controls_state()

    def _update_player_button_icon(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(QIcon(get_icon_file_path("pause.png")))
            self.play_button.setToolTip("Pause")
        else:
            self.play_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.play_button.setToolTip("Play")

    def _toggle_play_pause(self):
        if not self.current_loaded_track_meta_name or self.media_player.source().isEmpty():
            return
        state = self.media_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            if self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                if self.media_player.isSeekable(): self.media_player.setPosition(0)
            self.media_player.play()

    def _stop_playback(self, internal_call=False):
        if not internal_call and not self.current_loaded_track_meta_name: return

        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()

        if not internal_call:
            self.playback_slider.setValue(0)
            self.current_pos_label.setText(self._format_ms_time(0))
            self.update_controls_state()

    def update_controls_state(self):
        track_loaded_and_ready = (self.current_loaded_track_meta_name is not None and
                                  self.media_player.mediaStatus() in [
                                      QMediaPlayer.MediaStatus.LoadedMedia,
                                      QMediaPlayer.MediaStatus.BufferedMedia,
                                      QMediaPlayer.MediaStatus.BufferingMedia,
                                      QMediaPlayer.MediaStatus.EndOfMedia
                                  ])
        can_play_pause = track_loaded_and_ready
        can_stop = track_loaded_and_ready and self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState
        can_seek = track_loaded_and_ready and self.current_track_duration_ms_from_player > 0
        self.play_button.setEnabled(can_play_pause)
        self.stop_button.setEnabled(can_stop or (track_loaded_and_ready and self.media_player.position() > 0))
        self.playback_slider.setEnabled(can_seek)

    def get_current_track_duration_ms_from_player(self) -> int | None:
        # If current_track_duration_ms_from_player (set by durationChanged) is positive,
        # trust this value as the player has reported it.
        if self.current_track_duration_ms_from_player > 0:
            return self.current_track_duration_ms_from_player
        return None

    def _format_ms_time(self, ms):
        if ms < 0: ms = 0
        tot_secs = ms / 1000.0
        minutes = int(tot_secs // 60)
        seconds = tot_secs % 60
        return f"{minutes:02d}:{seconds:06.3f}"

    def set_volume(self, volume_float: float):
        if 0.0 <= volume_float <= 1.0:
            self.audio_output.setVolume(volume_float)
        else:
            logger.warning(f"SentenceVOPlayerPanel: Invalid volume {volume_float} requested.")