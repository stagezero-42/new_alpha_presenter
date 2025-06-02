# myapp/gui/audio_track_player_panel.py
import os
import logging
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..audio.audio_track_manager import AudioTrackManager  # To load full metadata if needed
from ..utils.paths import get_media_file_path, get_icon_file_path
from .widget_helpers import create_button

logger = logging.getLogger(__name__)


class AudioTrackPlayerPanel(QGroupBox):
    """
    Manages playback controls for a single selected audio track.
    """
    # Signal to request updating the track's start/end time in the main program data
    timing_update_requested = Signal(int, int)  # user_start_time_ms, user_end_time_ms (None for track end)

    def __init__(self, track_manager: AudioTrackManager, parent=None):
        super().__init__("Track Playback & Timing Tool", parent)
        self.track_manager = track_manager

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        # self.audio_output.setVolume(0.8) # Consider making this configurable

        self.current_track_metadata = None  # Full metadata of the loaded track
        self.current_track_entry_in_program = None  # Original entry from program (has user start/end)
        self.current_track_duration_ms_from_player = 0  # Duration from QMediaPlayer

        self._setup_ui()
        self._connect_signals()
        self.update_controls_state()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.loaded_track_label = QLabel("Loaded for Playback: None")
        layout.addWidget(self.loaded_track_label)

        self.playback_slider = QSlider(Qt.Orientation.Horizontal)
        self.playback_slider.setRange(0, 1000)  # Default range
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

        self.set_start_button = create_button("Set Start", on_click=self._set_current_pos_as_start)
        self.set_end_button = create_button("Set End", on_click=self._set_current_pos_as_end)
        controls_layout.addWidget(self.set_start_button)
        controls_layout.addWidget(self.set_end_button)
        layout.addLayout(controls_layout)

    def _connect_signals(self):
        self.playback_slider.sliderMoved.connect(self.media_player.setPosition)
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)
        self.media_player.mediaStatusChanged.connect(self._on_player_media_status_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)
        self.media_player.playbackStateChanged.connect(self._update_player_button_icon)

    def load_track_for_playback(self, track_entry_in_program: dict | None):
        self._stop_playback(internal_call=True)  # Stop current before loading new
        self.current_track_metadata = None
        self.current_track_entry_in_program = track_entry_in_program
        self.current_track_duration_ms_from_player = 0
        self._reset_ui_for_new_track()

        if not track_entry_in_program:
            self.update_controls_state()
            return

        track_metadata_name = track_entry_in_program.get("track_name")
        if not track_metadata_name:
            self.loaded_track_label.setText("Error: Track name missing in program entry.")
            self.update_controls_state()
            return

        logger.debug(f"TrackPlayerPanel: Attempting to load metadata for track: {track_metadata_name}")
        try:
            self.current_track_metadata = self.track_manager.load_track_metadata(track_metadata_name)
            if not self.current_track_metadata or not self.current_track_metadata.get("file_path"):
                self.loaded_track_label.setText(f"Error: Metadata/file_path missing for {track_metadata_name}")
                logger.warning(f"No file_path in metadata for track: {track_metadata_name}")
                self.current_track_metadata = None;
                self.update_controls_state();
                return

            media_file_name = self.current_track_metadata["file_path"]
            media_content_path = get_media_file_path(media_file_name)
            logger.info(f"TrackPlayerPanel: Attempting to set source for player: {media_content_path}")

            if os.path.exists(media_content_path):
                self.loaded_track_label.setText(f"Loading: {track_metadata_name}...")
                self.media_player.setSource(QUrl.fromLocalFile(media_content_path))
                # Duration and readiness handled by mediaStatusChanged
            else:
                self.loaded_track_label.setText(f"Error: File not found - {media_file_name}")
                logger.error(f"Audio file not found at expected path: {media_content_path}")
                self.current_track_metadata = None
        except Exception as e:
            logger.error(f"Exception loading track metadata '{track_metadata_name}' for playback: {e}", exc_info=True)
            self.loaded_track_label.setText(f"Error loading metadata: {track_metadata_name}")
            self.current_track_metadata = None

        self.update_controls_state()

    def _reset_ui_for_new_track(self):
        self.loaded_track_label.setText("Loaded for Playback: None")
        self.playback_slider.setValue(0)
        self.current_pos_label.setText(self._format_ms_time(0))
        self.total_duration_label.setText(f"/ {self._format_ms_time(0)}")
        self._update_player_button_icon()

    def _on_player_position_changed(self, position_ms):
        if not self.playback_slider.isSliderDown():  # Only update if user is not dragging
            self.playback_slider.setValue(position_ms)
        self.current_pos_label.setText(self._format_ms_time(position_ms))

    def _on_player_duration_changed(self, duration_ms):
        logger.debug(f"TrackPlayerPanel: Player duration changed: {duration_ms} ms")
        self.current_track_duration_ms_from_player = duration_ms if duration_ms > 0 else 0
        self.playback_slider.setRange(0,
                                      self.current_track_duration_ms_from_player if self.current_track_duration_ms_from_player > 0 else 1000)
        self.total_duration_label.setText(f"/ {self._format_ms_time(self.current_track_duration_ms_from_player)}")
        self.update_controls_state()

    def _on_player_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        track_name = self.current_track_metadata.get('track_name', 'N/A') if self.current_track_metadata else "N/A"
        logger.info(f"TrackPlayerPanel: MediaStatusChanged for '{track_name}': {status}")

        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.loaded_track_label.setText(f"Ready: {track_name}")
            # Apply user_start_time_ms from the program entry if available
            if self.current_track_entry_in_program and self.media_player.isSeekable():
                user_start_ms = self.current_track_entry_in_program.get("user_start_time_ms", 0)
                if user_start_ms > 0 and user_start_ms < self.media_player.duration():
                    logger.info(f"TrackPlayerPanel: Setting initial position to user_start_time_ms: {user_start_ms}")
                    self.media_player.setPosition(user_start_ms)
                    self.playback_slider.setValue(user_start_ms)  # Update slider too
            self.media_player.stop()  # Ensure it's primed in stopped state
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._update_player_button_icon()  # Show play icon
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            self._reset_ui_for_new_track()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.error(f"InvalidMedia status for track '{track_name}'")
            self.loaded_track_label.setText(f"Error: Invalid media for {track_name}")
            self.current_track_metadata = None  # Invalidate current track
        elif status == QMediaPlayer.MediaStatus.LoadingMedia:
            self.loaded_track_label.setText(f"Loading: {track_name}...")

        self.update_controls_state()

    def _on_player_error(self, error_enum, error_string=""):
        detailed_error_string = self.media_player.errorString()
        final_error_message = detailed_error_string if detailed_error_string else error_string
        track_name = self.current_track_metadata.get('track_name',
                                                     'Unknown') if self.current_track_metadata else 'Unknown'
        logger.error(f"TrackPlayerPanel: Error for track '{track_name}': {final_error_message} (Enum: {error_enum})")
        if error_enum != QMediaPlayer.Error.NoError:
            QMessageBox.warning(self, "Track Playback Error",
                                f"Could not play audio for '{track_name}':\n{final_error_message}")
        self.loaded_track_label.setText(f"Playback Error for: {track_name}")
        self.current_track_metadata = None
        self.update_controls_state()

    def _update_player_button_icon(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(QIcon(get_icon_file_path("pause.png")))
            self.play_button.setToolTip("Pause")
        else:
            self.play_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.play_button.setToolTip("Play")

    def _toggle_play_pause(self):
        if not self.current_track_metadata or self.media_player.source().isEmpty():
            QMessageBox.information(self, "No Track", "No track loaded for playback.")
            return

        state = self.media_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:  # Paused or Stopped
            # If at end, seek to start (or user_start_time_ms) before playing
            if self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                start_pos = self.current_track_entry_in_program.get("user_start_time_ms",
                                                                    0) if self.current_track_entry_in_program else 0
                if self.media_player.isSeekable(): self.media_player.setPosition(start_pos)
            self.media_player.play()
        self._update_player_button_icon()  # Should be handled by playbackStateChanged too

    def _stop_playback(self, internal_call=False):
        if not internal_call and not self.current_track_metadata: return  # No track to stop
        self.media_player.stop()  # This also sets position to 0
        self._update_player_button_icon()
        # Position and duration labels will update via signals
        # If called internally (e.g. when loading new track), don't need to update all controls yet.
        if not internal_call:
            self.playback_slider.setValue(0)  # Explicitly reset slider on manual stop
            self.current_pos_label.setText(self._format_ms_time(0))
            self.update_controls_state()

    def _set_current_pos_as_start(self):
        if not self.current_track_entry_in_program or not self.current_track_metadata:
            QMessageBox.warning(self, "No Track", "No track selected in program to set time for.")
            return

        current_pos_ms = self.media_player.position()
        # Emit signal to the main editor window to update the actual program data
        # The main editor will then call self.track_in_program_manager to update the table widget
        self.timing_update_requested.emit(current_pos_ms, self.current_track_entry_in_program.get("user_end_time_ms"))
        QMessageBox.information(self, "Time Set",
                                f"Start time marked at {self._format_ms_time(current_pos_ms)}.\nSave program to persist.")

    def _set_current_pos_as_end(self):
        if not self.current_track_entry_in_program or not self.current_track_metadata:
            QMessageBox.warning(self, "No Track", "No track selected in program to set time for.")
            return

        current_pos_ms = self.media_player.position()
        start_ms = self.current_track_entry_in_program.get("user_start_time_ms", 0)

        new_end_ms = None  # None means play to detected end
        if current_pos_ms <= 0 or current_pos_ms <= start_ms:  # Treat 0 or less than start as clearing custom end
            user_choice = QMessageBox.question(self, "Confirm End Time",
                                               "Clear custom end time? (Track will play to its detected end from start time)",
                                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                               QMessageBox.StandardButton.Yes)
            if user_choice == QMessageBox.StandardButton.No: return
            new_end_ms = None
        else:
            new_end_ms = current_pos_ms

        self.timing_update_requested.emit(start_ms, new_end_ms)
        display_time = "Track End" if new_end_ms is None else self._format_ms_time(new_end_ms)
        QMessageBox.information(self, "Time Set", f"End time marked at {display_time}.\nSave program to persist.")

    def update_controls_state(self):
        track_loaded_and_ready = (self.current_track_metadata is not None and
                                  self.media_player.mediaStatus() in [
                                      QMediaPlayer.MediaStatus.LoadedMedia,
                                      QMediaPlayer.MediaStatus.BufferedMedia,
                                      QMediaPlayer.MediaStatus.BufferingMedia,  # Allow interaction while buffering
                                      QMediaPlayer.MediaStatus.EndOfMedia
                                  ])

        can_play_pause = track_loaded_and_ready
        can_stop = track_loaded_and_ready and self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState
        can_seek = track_loaded_and_ready and self.current_track_duration_ms_from_player > 0
        can_set_times = track_loaded_and_ready and self.current_track_entry_in_program is not None

        self.play_button.setEnabled(can_play_pause)
        self.stop_button.setEnabled(can_stop or (
                    track_loaded_and_ready and self.media_player.position() > 0))  # Enable stop if played a bit then stopped
        self.playback_slider.setEnabled(can_seek)
        self.set_start_button.setEnabled(can_set_times)
        self.set_end_button.setEnabled(can_set_times)
        self.setEnabled(
            self.current_track_entry_in_program is not None)  # Disable whole group if no track from program selected

    def _format_ms_time(self, ms):
        if ms < 0: ms = 0  # Should not happen with QMediaPlayer position/duration
        tot_secs = ms / 1000.0
        minutes = int(tot_secs // 60)
        seconds = tot_secs % 60
        return f"{minutes:02d}:{seconds:06.3f}"  # SS.sss format for seconds

    def get_player_instance(self):  # Could be used by main window for global volume control later
        return self.media_player

    def get_audio_output_instance(self):
        return self.audio_output