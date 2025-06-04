# myapp/audio/slide_audio_player.py
import logging
import os
from PySide6.QtCore import QObject, QUrl, Signal, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..audio.audio_program_manager import AudioProgramManager
from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_media_file_path
from ..utils.schemas import DEFAULT_AUDIO_PROGRAM_VOLUME

logger = logging.getLogger(__name__)


class SlideAudioPlayer(QObject):
    playback_error_occurred = Signal(str)

    # audio_phase_completely_finished = Signal() # Consider for future ControlWindow integration

    def __init__(self, audio_program_manager: AudioProgramManager, audio_track_manager: AudioTrackManager, parent=None):
        super().__init__(parent)
        self.audio_program_manager = audio_program_manager
        self.audio_track_manager = audio_track_manager

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        # Default volume for the player itself, can be overridden by slide-specific setting.
        self.audio_output.setVolume(DEFAULT_AUDIO_PROGRAM_VOLUME)

        self.current_program_name = None
        self.current_program_data = None
        self.current_track_index_in_program = -1
        self.slide_should_loop_program = False
        self.is_playing_audio_content = False
        self._is_stopping_intentionally = False
        self._custom_end_timer = None

        self._intro_delay_ms = 0
        self._outro_duration_ms = 0
        self._current_slide_audio_volume = DEFAULT_AUDIO_PROGRAM_VOLUME  # NEW
        self._intro_delay_timer = QTimer(self)
        self._intro_delay_timer.setSingleShot(True)
        self._intro_delay_timer.timeout.connect(self._start_actual_playback_after_intro)
        self._outro_timer = QTimer(self)
        self._outro_timer.setSingleShot(True)
        self._outro_timer.timeout.connect(self._finish_outro_and_slide_loop_logic)
        self._is_in_outro_phase = False

        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)

        logger.debug("SlideAudioPlayer initialized.")

    def load_program_and_play(self, slide_audio_config: dict):
        logger.info(f"Attempting to load audio with config: {slide_audio_config}")
        self.stop()

        if not slide_audio_config or not isinstance(slide_audio_config, dict):
            logger.debug("No valid slide_audio_config provided.")
            return

        program_name = slide_audio_config.get("audio_program_name")
        if not program_name:
            logger.debug("No audio program name in config.")
            return

        self.slide_should_loop_program = slide_audio_config.get("loop_audio_program", False)
        self._intro_delay_ms = slide_audio_config.get("audio_intro_delay_ms", 0)
        self._outro_duration_ms = slide_audio_config.get("audio_outro_duration_ms", 0)
        self._current_slide_audio_volume = slide_audio_config.get("audio_program_volume",
                                                                  DEFAULT_AUDIO_PROGRAM_VOLUME)  # NEW

        # Apply slide-specific volume
        self.audio_output.setVolume(self._current_slide_audio_volume)
        logger.debug(f"Applied slide-specific volume: {self._current_slide_audio_volume}")

        try:
            self.current_program_data = self.audio_program_manager.load_program(program_name)
            if not self.current_program_data or not self.current_program_data.get("tracks"):
                logger.warning(f"Audio program '{program_name}' not found or has no tracks.")
                self.playback_error_occurred.emit(f"Audio program '{program_name}' not found or empty.")
                self._clear_internal_state()
                return
        except Exception as e:
            logger.error(f"Error loading program '{program_name}': {e}", exc_info=True)
            self.playback_error_occurred.emit(f"Error loading program '{program_name}'.")
            self._clear_internal_state()
            return

        self.current_program_name = program_name
        self.current_track_index_in_program = -1

        if self._intro_delay_ms > 0:
            logger.info(f"Starting intro delay of {self._intro_delay_ms}ms for '{program_name}'.")
            self._intro_delay_timer.start(self._intro_delay_ms)
        else:
            logger.debug(f"No intro delay for '{program_name}'. Starting playback directly.")
            self._start_actual_playback_after_intro()

    def _start_actual_playback_after_intro(self):
        logger.debug(f"Intro delay finished (or was zero). Starting actual playback for '{self.current_program_name}'.")
        if not self.current_program_name:
            logger.warning("Actual playback start aborted, program name cleared.")
            return
        # Re-apply volume in case it was changed elsewhere, or for clarity
        self.audio_output.setVolume(self._current_slide_audio_volume)
        self._play_next_track_in_program()

    def _play_next_track_in_program(self):
        if self._custom_end_timer and self._custom_end_timer.isActive():
            self._custom_end_timer.stop()
        self._custom_end_timer = None

        if not self.current_program_data or not self.current_program_data.get("tracks"):
            logger.debug("No program data or tracks for _play_next_track_in_program.")
            self._handle_program_content_finished()
            return

        program_tracks = sorted(self.current_program_data.get("tracks", []), key=lambda t: t.get("play_order", 0))
        self.current_track_index_in_program += 1

        if self.current_track_index_in_program >= len(program_tracks):
            logger.info(f"Finished all tracks in program '{self.current_program_name}'.")
            self._handle_program_content_finished()
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
                QTimer.singleShot(0, self._play_next_track_in_program)
                return

            media_content_path = get_media_file_path(track_metadata["file_path"])
            if not os.path.exists(media_content_path):
                logger.error(f"Audio file not found: {media_content_path}. Skipping.")
                self.playback_error_occurred.emit(f"File not found for '{track_metadata_name}'.")
                QTimer.singleShot(0, self._play_next_track_in_program)
                return

            logger.debug(f"Setting source for player: {media_content_path}")
            # Volume is already set for the slide by load_program_and_play or _start_actual_playback_after_intro
            self.media_player.setSource(QUrl.fromLocalFile(media_content_path))
        except Exception as e:
            logger.error(f"Error loading metadata for '{track_metadata_name}': {e}", exc_info=True)
            self.playback_error_occurred.emit(f"Error loading track '{track_metadata_name}'.")
            QTimer.singleShot(0, self._play_next_track_in_program)

    def _handle_program_content_finished(self):
        logger.debug(f"Program content '{self.current_program_name}' finished.")
        self.is_playing_audio_content = False

        if self._is_stopping_intentionally:
            logger.debug("Program content finished during intentional stop. No further action.")
            return

        if self._outro_duration_ms > 0 and not self._is_in_outro_phase:
            logger.info(f"Starting outro duration of {self._outro_duration_ms}ms for '{self.current_program_name}'.")
            self._is_in_outro_phase = True
            # Player should be stopped or at end of media here. Outro is a conceptual delay.
            if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                self.media_player.stop()
            self._outro_timer.start(self._outro_duration_ms)
        else:
            self._finish_outro_and_slide_loop_logic()

    def _finish_outro_and_slide_loop_logic(self):
        logger.debug(f"Outro finished or skipped. Processing slide loop for '{self.current_program_name}'.")
        self._is_in_outro_phase = False

        if self._is_stopping_intentionally:
            logger.debug("Outro/Slide loop logic aborted due to intentional stop.")
            return

        if self.slide_should_loop_program and self.current_program_name:
            logger.info(f"Looping audio program '{self.current_program_name}' for slide.")
            self.current_track_index_in_program = -1
            if self._intro_delay_ms > 0:
                logger.info(
                    f"Restarting intro delay of {self._intro_delay_ms}ms for looped program '{self.current_program_name}'.")
                self._intro_delay_timer.start(self._intro_delay_ms)
            else:
                QTimer.singleShot(0, self._start_actual_playback_after_intro)
        else:
            logger.info(
                f"Program '{self.current_program_name or 'Unknown'}' finished its full cycle (including any outro), not looping for slide.")
            if not self._is_stopping_intentionally:
                self.stop()
            # self.audio_phase_completely_finished.emit()

    def _clear_internal_state(self):
        self.current_program_name = None
        self.current_program_data = None
        self.current_track_index_in_program = -1
        self.is_playing_audio_content = False
        self._is_in_outro_phase = False
        self._intro_delay_ms = 0
        self._outro_duration_ms = 0
        self._current_slide_audio_volume = DEFAULT_AUDIO_PROGRAM_VOLUME  # Reset to default

    def stop(self):
        prog_name_at_stop_call = self.current_program_name
        logger.info(
            f"SlideAudioPlayer: Stop cmd. CurrentProg='{prog_name_at_stop_call}', Idx={self.current_track_index_in_program}, PlayerState={self.media_player.playbackState()}")

        if self._is_stopping_intentionally:
            logger.debug("Stop called while already in a stopping sequence. Returning.")
            return
        self._is_stopping_intentionally = True

        if self._intro_delay_timer.isActive(): self._intro_delay_timer.stop(); logger.debug("Intro timer stopped.")
        if self._outro_timer.isActive(): self._outro_timer.stop(); logger.debug("Outro timer stopped.")
        if self._custom_end_timer and self._custom_end_timer.isActive(): self._custom_end_timer.stop(); logger.debug(
            "Custom end timer stopped.")
        self._custom_end_timer = None

        player_state_before_stop = self.media_player.playbackState()
        source_before_clear = self.media_player.source()

        if player_state_before_stop != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
            logger.debug(f"Player explicitly stopped. Was playing/paused: '{source_before_clear.fileName()}'.")

        if source_before_clear.isValid() and not source_before_clear.isEmpty():
            self.media_player.setSource(QUrl())
            logger.debug(f"Player source '{source_before_clear.fileName()}' cleared.")

        self.audio_output.setVolume(DEFAULT_AUDIO_PROGRAM_VOLUME)  # Reset to default player volume on stop
        logger.debug(f"Audio output volume reset to default: {DEFAULT_AUDIO_PROGRAM_VOLUME}")

        self._clear_internal_state()

        logger.debug(
            f"SlideAudioPlayer context cleared for '{prog_name_at_stop_call or 'previous program'}'. Now stopped.")
        self._is_stopping_intentionally = False

    def _get_expected_current_track_details(self):
        if not self.current_program_data or not self.current_program_data.get("tracks") or \
                self.current_track_index_in_program < 0 or \
                self.current_track_index_in_program >= len(self.current_program_data.get("tracks", [])):
            return None, None

        program_tracks = sorted(self.current_program_data["tracks"], key=lambda t: t.get("play_order", 0))
        if not (0 <= self.current_track_index_in_program < len(program_tracks)):
            return None, None

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
            self.media_player.stop()
            logger.debug(f"Player stopped (priming) after LoadedMedia for '{current_expected_track_name}'.")
            if self.media_player.isSeekable() and user_start_ms > 0:
                self.media_player.setPosition(user_start_ms)
                logger.debug(f"Position set to {user_start_ms}ms for '{current_expected_track_name}'.")
            # Volume already set by load_program_and_play or _start_actual_playback_after_intro
            self.media_player.play()
            logger.debug(f"Play command issued for '{current_expected_track_name}' after priming.")

        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if not current_track_entry or not current_expected_abs_path or \
                    os.path.normpath(player_source_path) != os.path.normpath(current_expected_abs_path):
                logger.warning(
                    f"EndOfMedia for '{os.path.basename(player_source_path)}' does NOT match expected track '{current_expected_track_name}'. Ignoring advance.")
                return
            logger.info(f"EndOfMedia for track '{current_expected_track_name}'. Playing next.")
            self.is_playing_audio_content = False
            self._play_next_track_in_program()

        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.error(f"InvalidMedia for '{current_expected_track_name}'. Source: {player_source_path}")
            self.playback_error_occurred.emit(f"Invalid media for track '{current_expected_track_name}'.")
            self.is_playing_audio_content = False
            self._play_next_track_in_program()

        elif status == QMediaPlayer.MediaStatus.NoMedia:
            logger.debug(f"MediaStatus.NoMedia. Expected track context: '{current_expected_track_name}'.")
            self.is_playing_audio_content = False

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        expected_track_entry, _ = self._get_expected_current_track_details()
        track_name_for_log = expected_track_entry.get("track_name") if expected_track_entry else "N/A"
        logger.debug(
            f"PlaybackStateChanged for '{track_name_for_log}': {state}, stopping_flag={self._is_stopping_intentionally}")

        if self._is_stopping_intentionally and state == QMediaPlayer.PlaybackState.StoppedState:
            logger.debug(f"  -> StoppedState for '{track_name_for_log}' ignored (intentional stop in progress).")
            return

        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.is_playing_audio_content = True
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
                                f"Track '{track_name_for_log}' custom end timer set for {segment_duration_ms}ms.")
                    else:
                        QTimer.singleShot(0, self._handle_custom_end_time)

        elif state == QMediaPlayer.PlaybackState.StoppedState:
            # Check if this stop was due to an error handled by _on_player_error
            # or if it's an EndOfMedia handled by _on_media_status_changed
            if self.media_player.error() == QMediaPlayer.Error.NoError and \
                    self.media_player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia and \
                    not self._is_stopping_intentionally:
                # This is an unexpected stop not covered by other handlers.
                logger.warning(
                    f"Playback for '{track_name_for_log}' stopped unexpectedly. Was playing: {self.is_playing_audio_content}")
                # If it was supposed to be playing (e.g. not paused or end of media), then advance.
                if self.is_playing_audio_content:  # and self.current_program_name:
                    QTimer.singleShot(0, self._play_next_track_in_program)

            self.is_playing_audio_content = False  # Always update this on stop
            # logger.info(f"Playback stopped for '{track_name_for_log}'. Pos: {self.media_player.position()}, MediaStatus: {self.media_player.mediaStatus()}")


        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.is_playing_audio_content = False
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

        # Check if the player is actually playing the intended track.
        # This is a safeguard against the timer firing after context has changed (e.g., stop() called then quickly play() again)
        if not self.is_playing_audio_content and self.media_player.playbackState() != QMediaPlayer.PlayingState:
            # Further check: if the source has changed, this timer is definitely stale.
            if not self.media_player.source().isEmpty() and self._get_expected_current_track_details()[
                1] != self.media_player.source().toLocalFile():
                logger.debug(f"Custom end timer for '{track_name_for_log}' fired, but source changed. Ignoring.")
                return

            logger.debug(
                f"Custom end timer for '{track_name_for_log}' fired, but player not actively playing or source mismatch. Ignoring advance.");
            return

        logger.info(f"Custom end time reached for track '{track_name_for_log}'. Stopping current track and advancing.")
        temp_stopping_flag = self._is_stopping_intentionally
        self._is_stopping_intentionally = True
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState: self.media_player.stop()
        self.is_playing_audio_content = False
        self._is_stopping_intentionally = temp_stopping_flag
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
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState: self.media_player.stop()
        self.is_playing_audio_content = False
        self._is_stopping_intentionally = temp_stopping_flag
        self._play_next_track_in_program()

    def is_audio_active(self) -> bool:
        return self._intro_delay_timer.isActive() or self.is_playing_audio_content or self._is_in_outro_phase