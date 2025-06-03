# myapp/audio/slide_audio_player.py
import logging
import os
from PySide6.QtCore import QObject, QUrl, Signal, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..audio.audio_program_manager import AudioProgramManager
from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_media_file_path

logger = logging.getLogger(__name__)


class SlideAudioPlayer(QObject):
    playback_error_occurred = Signal(str)

    def __init__(self, audio_program_manager: AudioProgramManager, audio_track_manager: AudioTrackManager, parent=None):
        super().__init__(parent)
        self.audio_program_manager = audio_program_manager
        self.audio_track_manager = audio_track_manager

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self.current_program_name = None
        self.current_program_data = None
        self.current_track_index_in_program = -1
        self.slide_should_loop_program = False
        self.is_playing = False
        self._is_stopping_intentionally = False
        self._custom_end_timer = None

        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)
        # Removed self.media_player.positionChanged.connect(self._check_custom_end_time_on_position_change)
        # as _check_custom_end_time_on_position_change was 'pass' and QTimer is preferred.

        logger.debug("SlideAudioPlayer initialized.")

    def load_program_and_play(self, program_name: str, loop_slide_audio: bool):
        logger.info(f"Attempting to load audio program: '{program_name}', Loop: {loop_slide_audio}")
        self.stop()

        if not program_name:
            logger.debug("No audio program name provided.")
            return

        try:
            self.current_program_data = self.audio_program_manager.load_program(program_name)
            if not self.current_program_data or not self.current_program_data.get("tracks"):
                logger.warning(f"Audio program '{program_name}' not found or has no tracks.")
                self.playback_error_occurred.emit(f"Audio program '{program_name}' not found or empty.")
                self.current_program_data = None  # Ensure cleared
                return
        except Exception as e:
            logger.error(f"Error loading program '{program_name}': {e}", exc_info=True)
            self.playback_error_occurred.emit(f"Error loading program '{program_name}'.")
            self.current_program_data = None  # Ensure cleared
            return

        self.current_program_name = program_name
        self.slide_should_loop_program = loop_slide_audio
        self.current_track_index_in_program = -1  # Reset for new program
        self._play_next_track_in_program()

    def _play_next_track_in_program(self):
        if self._custom_end_timer and self._custom_end_timer.isActive():
            self._custom_end_timer.stop()
        self._custom_end_timer = None

        if not self.current_program_data or not self.current_program_data.get("tracks"):
            logger.debug("No program data or tracks for _play_next_track_in_program.")
            self._handle_program_finished()
            return

        program_tracks = sorted(self.current_program_data.get("tracks", []), key=lambda t: t.get("play_order", 0))
        self.current_track_index_in_program += 1

        if self.current_track_index_in_program >= len(program_tracks):
            logger.info(f"Finished all tracks in program '{self.current_program_name}'.")
            self._handle_program_finished()
            return

        track_entry = program_tracks[self.current_track_index_in_program]
        track_metadata_name = track_entry.get("track_name")

        logger.info(
            f"Preparing track {self.current_track_index_in_program + 1}/{len(program_tracks)}: '{track_metadata_name}' from '{self.current_program_name}'.")

        try:
            track_metadata = self.audio_track_manager.load_track_metadata(track_metadata_name)
            if not track_metadata or not track_metadata.get("file_path"):
                logger.warning(f"Metadata/file_path missing for track '{track_metadata_name}'. Skipping.")
                self.playback_error_occurred.emit(f"Metadata missing for '{track_metadata_name}'.")
                QTimer.singleShot(0, self._play_next_track_in_program);
                return  # Use QTimer to avoid deep recursion

            media_content_path = get_media_file_path(track_metadata["file_path"])
            if not os.path.exists(media_content_path):
                logger.error(f"Audio file not found: {media_content_path}. Skipping.")
                self.playback_error_occurred.emit(f"File not found for '{track_metadata_name}'.")
                QTimer.singleShot(0, self._play_next_track_in_program);
                return

            logger.debug(f"Setting source for player: {media_content_path}")
            self.media_player.setSource(QUrl.fromLocalFile(media_content_path))
        except Exception as e:
            logger.error(f"Error loading metadata for '{track_metadata_name}': {e}", exc_info=True)
            self.playback_error_occurred.emit(f"Error loading track '{track_metadata_name}'.")
            QTimer.singleShot(0, self._play_next_track_in_program)

    def _handle_program_finished(self):
        logger.debug(f"Program '{self.current_program_name}' processing finished.")
        if self.slide_should_loop_program and self.current_program_name:  # Check current_program_name as stop() clears it
            logger.info(f"Looping audio program '{self.current_program_name}'.")
            self.current_track_index_in_program = -1
            # Use QTimer to avoid potential deep recursion if all tracks are 0-duration or fail instantly
            QTimer.singleShot(0, self._play_next_track_in_program)
        else:
            logger.info(
                f"Program '{self.current_program_name if self.current_program_name else 'Unknown'}' finished, not looping for slide.")
            # Call stop only if not already in a stop sequence to avoid re-entrancy issues with the flag
            if not self._is_stopping_intentionally:
                self.stop()

    def stop(self):
        # Store local copy of program name for logging, as instance var will be cleared.
        prog_name_at_stop_call = self.current_program_name
        logger.info(
            f"SlideAudioPlayer: Stop cmd. CurrentProg='{prog_name_at_stop_call}', Idx={self.current_track_index_in_program}, PlayingState={self.media_player.playbackState()}")

        if self._is_stopping_intentionally:  # Avoid re-entrant stop calls if already stopping
            logger.debug("Stop called while already in a stopping sequence. Returning.")
            return
        self._is_stopping_intentionally = True

        # Clear internal program context *before* player operations
        # This helps stale signals not match the (now invalid) context.
        self.current_program_name = None
        self.current_program_data = None
        self.current_track_index_in_program = -1

        if self._custom_end_timer and self._custom_end_timer.isActive():
            self._custom_end_timer.stop()
            logger.debug(f"Custom end timer for '{prog_name_at_stop_call or 'previous track'}' stopped.")
        self._custom_end_timer = None

        player_state_before_stop = self.media_player.playbackState()
        source_before_clear = self.media_player.source()

        if player_state_before_stop != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
            logger.debug(
                f"Player explicitly stopped. Was playing/paused: '{source_before_clear.fileName()}'. New state: {self.media_player.playbackState()}")

        if source_before_clear.isValid() and not source_before_clear.isEmpty():
            self.media_player.setSource(QUrl())
            logger.debug(
                f"Player source '{source_before_clear.fileName()}' cleared. New source: {self.media_player.source().fileName()}")

        self.is_playing = False  # Final state

        logger.debug(
            f"SlideAudioPlayer context cleared for '{prog_name_at_stop_call or 'previous program'}'. Now stopped.")
        self._is_stopping_intentionally = False

    def _get_expected_current_track_details(self):
        if not self.current_program_data or not self.current_program_data.get("tracks") or \
                self.current_track_index_in_program < 0 or \
                self.current_track_index_in_program >= len(self.current_program_data.get("tracks", [])):
            return None, None

        program_tracks = sorted(self.current_program_data["tracks"], key=lambda t: t.get("play_order", 0))
        # Check index again after sort, though play_order should map to list index if correctly maintained
        if not (0 <= self.current_track_index_in_program < len(program_tracks)):
            return None, None  # Should not happen if initial checks passed and data is consistent

        track_entry = program_tracks[self.current_track_index_in_program]

        try:
            track_metadata = self.audio_track_manager.load_track_metadata(track_entry.get("track_name"))
            if track_metadata and track_metadata.get("file_path"):
                abs_path = get_media_file_path(track_metadata["file_path"])
                return track_entry, abs_path
        except Exception as e:
            logger.error(f"Error getting expected track details for {track_entry.get('track_name')}: {e}")
        return track_entry, None

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        player_source_path = self.media_player.source().toLocalFile()
        log_track_entry, _ = self._get_expected_current_track_details()
        log_track_name = log_track_entry.get("track_name") if log_track_entry else "N/A"
        logger.debug(
            f"MediaStatusChanged for player source '{os.path.basename(player_source_path)}' (current context: '{log_track_name}'): {status}, stopping_flag={self._is_stopping_intentionally}")

        if self._is_stopping_intentionally:
            logger.debug(f"  -> Ignored (intentional stop in progress).")
            return

        current_track_entry, current_expected_abs_path = self._get_expected_current_track_details()
        current_expected_track_name = current_track_entry.get("track_name") if current_track_entry else "N/A"

        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if not current_track_entry:
                logger.debug(
                    f"  -> LoadedMedia for '{os.path.basename(player_source_path)}' ignored (no active program context after checks).")
                return

            if not current_expected_abs_path or \
                    os.path.normpath(player_source_path) != os.path.normpath(current_expected_abs_path):
                logger.warning(
                    f"  -> LoadedMedia for '{os.path.basename(player_source_path)}' does NOT match current expected track '{current_expected_track_name}' ('{os.path.basename(str(current_expected_abs_path))}'). Ignoring.")
                return

            logger.info(f"Media loaded for intended track '{current_expected_track_name}'. Priming and playing.")
            user_start_ms = current_track_entry.get("user_start_time_ms", 0)

            # Proactive stop to prime the player
            self.media_player.stop()
            logger.debug(
                f"Player stopped (priming) after LoadedMedia for '{current_expected_track_name}'. State: {self.media_player.playbackState()}")

            if self.media_player.isSeekable() and user_start_ms > 0:
                self.media_player.setPosition(user_start_ms)
                logger.debug(f"Position set to {user_start_ms}ms for '{current_expected_track_name}'.")

            self.media_player.play()
            logger.debug(
                f"Play command issued for '{current_expected_track_name}' after priming stop. Player state: {self.media_player.playbackState()}")

        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if not current_track_entry or not current_expected_abs_path or \
                    os.path.normpath(player_source_path) != os.path.normpath(current_expected_abs_path):
                logger.warning(
                    f"EndOfMedia for '{os.path.basename(player_source_path)}' does NOT match expected track '{current_expected_track_name}'. Ignoring advance.")
                return

            logger.info(f"EndOfMedia for track '{current_expected_track_name}'. Playing next.")
            self.is_playing = False
            self._play_next_track_in_program()

        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.error(f"InvalidMedia for '{current_expected_track_name}'. Source: {player_source_path}")
            self.playback_error_occurred.emit(f"Invalid media for track '{current_expected_track_name}'.")
            self.is_playing = False
            self._play_next_track_in_program()

        elif status == QMediaPlayer.MediaStatus.NoMedia:
            logger.debug(f"MediaStatus.NoMedia. Expected track context: '{current_expected_track_name}'.")
            self.is_playing = False

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        expected_track_entry, _ = self._get_expected_current_track_details()
        track_name_for_log = expected_track_entry.get("track_name") if expected_track_entry else "N/A"
        logger.debug(
            f"PlaybackStateChanged for '{track_name_for_log}': {state}, stopping_flag={self._is_stopping_intentionally}")

        if self._is_stopping_intentionally and state == QMediaPlayer.PlaybackState.StoppedState:
            logger.debug(f"  -> StoppedState for '{track_name_for_log}' ignored (intentional stop in progress).")
            return

        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.is_playing = True
            logger.info(f"Playback started/resumed for '{track_name_for_log}'.")

            if self._custom_end_timer and self._custom_end_timer.isActive(): self._custom_end_timer.stop()
            self._custom_end_timer = None

            if expected_track_entry:
                user_end_ms = expected_track_entry.get("user_end_time_ms")
                if user_end_ms is not None and user_end_ms > 0:
                    current_pos_ms = self.media_player.position()
                    start_ms_for_track = expected_track_entry.get("user_start_time_ms", 0)
                    effective_start_ms = max(current_pos_ms,
                                             start_ms_for_track) if current_pos_ms >= start_ms_for_track else start_ms_for_track

                    if user_end_ms > effective_start_ms:
                        segment_duration_ms = user_end_ms - effective_start_ms
                        if segment_duration_ms > 0:
                            self._custom_end_timer = QTimer(self)
                            self._custom_end_timer.setSingleShot(True)
                            self._custom_end_timer.timeout.connect(self._handle_custom_end_time)
                            self._custom_end_timer.start(segment_duration_ms)
                            logger.debug(
                                f"Track '{track_name_for_log}' has custom end. Timer set for {segment_duration_ms}ms from effective start {effective_start_ms}ms.")
                    else:
                        logger.warning(
                            f"Track '{track_name_for_log}' custom end {user_end_ms}ms is <= effective start {effective_start_ms}ms. Will advance/ignore.")
                        QTimer.singleShot(0, self._handle_custom_end_time)  # Advance effectively immediately

        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.is_playing = False
            logger.info(
                f"Playback stopped for '{track_name_for_log}'. Pos: {self.media_player.position()}, MediaStatus: {self.media_player.mediaStatus()}")
            # EndOfMedia status change handles advancing. This handles other stops.
            if not self._is_stopping_intentionally and self.media_player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia:
                if self.current_program_name and self.media_player.error() == QMediaPlayer.Error.NoError:  # Still in a program context and no player error
                    logger.warning(
                        f"Playback for '{track_name_for_log}' stopped unexpectedly. Attempting to advance program.")
                    # QTimer.singleShot(0, self._play_next_track_in_program) # Using QTimer to avoid direct re-entrant calls
                elif self.media_player.error() != QMediaPlayer.Error.NoError:
                    logger.error(
                        f"Playback for '{track_name_for_log}' stopped due to player error: {self.media_player.errorString()}")

        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.is_playing = False
            logger.info(f"Playback paused for '{track_name_for_log}'.")
            if self._custom_end_timer and self._custom_end_timer.isActive():
                self._custom_end_timer.stop();
                logger.debug("Custom end timer paused.")

    def _handle_custom_end_time(self):
        if self._is_stopping_intentionally:
            logger.debug("Custom end timer fired, but intentional stop in progress. Ignoring.");
            return

        expected_track_entry, _ = self._get_expected_current_track_details()
        track_name_for_log = expected_track_entry.get("track_name") if expected_track_entry else "N/A"

        if not self.is_playing and self.media_player.playbackState() != QMediaPlayer.PlayingState:
            logger.debug(
                f"Custom end timer for '{track_name_for_log}' fired, but player not actively playing. Ignoring advance.");
            return

        logger.info(f"Custom end time reached for track '{track_name_for_log}'. Stopping current track and advancing.")

        temp_stopping_flag = self._is_stopping_intentionally
        self._is_stopping_intentionally = True  # Prevent loops during this stop
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
        self.is_playing = False
        self._is_stopping_intentionally = temp_stopping_flag  # Restore previous flag state

        self._play_next_track_in_program()

    def _on_player_error(self, error_enum):
        error_string = self.media_player.errorString()
        logger.error(f"SlideAudioPlayer QMediaPlayer Error: {error_enum}, String: '{error_string}'")

        expected_track_entry, _ = self._get_expected_current_track_details()
        track_name_for_log = expected_track_entry.get("track_name") if expected_track_entry else "N/A"

        final_error_message = error_string if error_string else f"Unknown player error ({error_enum}) for track '{track_name_for_log}'."
        self.playback_error_occurred.emit(final_error_message)

        logger.info(f"Error during playback of '{track_name_for_log}'. Attempting next track.")

        temp_stopping_flag = self._is_stopping_intentionally
        self._is_stopping_intentionally = True
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
        self.is_playing = False
        self._is_stopping_intentionally = temp_stopping_flag

        self._play_next_track_in_program()