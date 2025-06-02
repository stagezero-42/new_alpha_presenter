# myapp/audio/audio_player_manager.py
import os
import logging
from PySide6.QtCore import QObject, Signal, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..audio.audio_program_manager import AudioProgramManager
from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_media_file_path

logger = logging.getLogger(__name__)


class AudioPlayerManager(QObject):
    """
    Manages the playback of an entire audio program, including
    sequential track playback and program looping.
    """
    program_playback_finished = Signal()  # Emitted when the whole program (including loops) finishes
    playback_error_occurred = Signal(str)  # Emitted with an error message
    current_track_changed = Signal(str)  # Emitted with the name of the new track starting

    def __init__(self, program_manager: AudioProgramManager, track_manager: AudioTrackManager, parent=None):
        super().__init__(parent)
        self.program_manager = program_manager
        self.track_manager = track_manager

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)  # Default audio output
        self.media_player.setAudioOutput(self.audio_output)

        self._current_program_data = None
        self._track_queue = []  # List of (track_meta, effective_start_ms, effective_duration_ms)
        self._current_track_index_in_queue = -1

        self._loop_indefinitely = False
        self._loop_count_remaining = 0
        self._initial_loop_count = 0

        self._is_playing = False
        self._is_paused = False  # To differentiate stop from pause

        self.media_player.mediaStatusChanged.connect(self._handle_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._handle_playback_state_changed)
        self.media_player.errorOccurred.connect(self._handle_player_error)

        # Timer for delayed start of the next track if needed (e.g. to simulate gaps)
        # For now, we'll play tracks back-to-back. This could be enhanced later.
        # self._next_track_delay_timer = QTimer(self)
        # self._next_track_delay_timer.setSingleShot(True)
        # self._next_track_delay_timer.timeout.connect(self._play_current_track_in_queue)

    def load_program(self, program_name: str) -> bool:
        logger.info(f"AudioPlayerManager: Loading program '{program_name}'")
        self.stop()  # Stop any current playback
        self._track_queue = []
        self._current_track_index_in_queue = -1
        self._current_program_data = None

        try:
            program_data = self.program_manager.load_program(program_name)
            if not program_data:
                logger.error(f"AudioPlayerManager: Program '{program_name}' not found or failed to load.")
                return False

            self._current_program_data = program_data
            self._loop_indefinitely = program_data.get("loop_indefinitely", False)
            self._initial_loop_count = program_data.get("loop_count", 0)
            self._loop_count_remaining = self._initial_loop_count

            tracks_in_program = sorted(program_data.get("tracks", []), key=lambda t: t.get("play_order", 0))

            for track_entry in tracks_in_program:
                track_meta_name = track_entry.get("track_name")
                if not track_meta_name:
                    logger.warning("AudioPlayerManager: Track entry missing track_name, skipping.")
                    continue

                track_meta = self.track_manager.load_track_metadata(track_meta_name)
                if not track_meta or not track_meta.get("file_path"):
                    logger.warning(
                        f"AudioPlayerManager: Metadata or file_path missing for track '{track_meta_name}', skipping.")
                    continue

                media_file_abs_path = get_media_file_path(track_meta["file_path"])
                if not os.path.exists(media_file_abs_path):
                    logger.warning(
                        f"AudioPlayerManager: Media file '{media_file_abs_path}' not found for track '{track_meta_name}', skipping.")
                    continue

                track_meta["_abs_path"] = media_file_abs_path  # Store for easy access

                user_start_ms = track_entry.get("user_start_time_ms", 0)
                user_end_ms = track_entry.get("user_end_time_ms")  # Can be None
                detected_duration_ms = track_meta.get("detected_duration_ms")

                effective_start_ms = user_start_ms
                effective_duration_ms = None

                if detected_duration_ms is not None:
                    if user_end_ms is not None and user_end_ms > user_start_ms:
                        effective_duration_ms = user_end_ms - user_start_ms
                    else:  # Play from user_start_ms to detected end
                        effective_duration_ms = detected_duration_ms - user_start_ms

                    if effective_duration_ms <= 0:
                        logger.warning(
                            f"AudioPlayerManager: Track '{track_meta_name}' has non-positive effective duration after user times, skipping.")
                        continue
                else:  # No detected duration, cannot honor user_end_time_ms reliably
                    logger.warning(
                        f"AudioPlayerManager: Track '{track_meta_name}' has no detected duration. Will play full file from user_start_time_ms if possible.")
                    # effective_duration_ms remains None, player will play until actual end or error

                self._track_queue.append({
                    "meta": track_meta,
                    "effective_start_ms": effective_start_ms,
                    "effective_duration_ms": effective_duration_ms  # This being None means play until end of file
                })

            if not self._track_queue:
                logger.warning(f"AudioPlayerManager: No playable tracks found in program '{program_name}'.")
                return False

            logger.info(f"AudioPlayerManager: Program '{program_name}' loaded with {len(self._track_queue)} tracks.")
            return True

        except Exception as e:
            logger.error(f"AudioPlayerManager: Error loading program '{program_name}': {e}", exc_info=True)
            self.playback_error_occurred.emit(f"Error loading audio program: {program_name}")
            return False

    def play(self):
        if not self._track_queue:
            logger.info("AudioPlayerManager: Play called but no tracks in queue.")
            self.program_playback_finished.emit()  # Nothing to play
            return

        if self._is_playing and not self._is_paused:
            logger.debug("AudioPlayerManager: Already playing.")
            return

        if self._is_paused:  # Resuming
            logger.info("AudioPlayerManager: Resuming playback.")
            self.media_player.play()
            self._is_paused = False
            self._is_playing = True
        else:  # Starting fresh or from a stopped state
            logger.info("AudioPlayerManager: Starting playback of program.")
            self._current_track_index_in_queue = 0
            self._loop_count_remaining = self._initial_loop_count  # Reset loop count for new program play
            self._play_current_track_in_queue()
            self._is_playing = True
            self._is_paused = False

    def _play_current_track_in_queue(self):
        if not (0 <= self._current_track_index_in_queue < len(self._track_queue)):
            self._handle_program_end()
            return

        track_info = self._track_queue[self._current_track_index_in_queue]
        track_meta = track_info["meta"]
        abs_path = track_meta["_abs_path"]
        start_pos_ms = track_info["effective_start_ms"]

        logger.info(
            f"AudioPlayerManager: Playing track {self._current_track_index_in_queue + 1}/{len(self._track_queue)}: '{track_meta['track_name']}' from {abs_path} at {start_pos_ms}ms")
        self.current_track_changed.emit(track_meta['track_name'])

        self.media_player.setSource(QUrl.fromLocalFile(abs_path))
        # Position setting must happen *after* media is loaded or in LoadedMedia state.
        # We'll handle it in _handle_media_status_changed.

    def _handle_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        logger.debug(
            f"AudioPlayerManager: Media status changed to {status} for source {self.media_player.source().fileName()}")
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if 0 <= self._current_track_index_in_queue < len(self._track_queue):
                track_info = self._track_queue[self._current_track_index_in_queue]
                start_pos_ms = track_info["effective_start_ms"]

                if self.media_player.isSeekable() and start_pos_ms > 0:
                    logger.debug(
                        f"AudioPlayerManager: Seeking to {start_pos_ms}ms for track '{track_info['meta']['track_name']}'")
                    self.media_player.setPosition(start_pos_ms)

                # If effective_duration_ms is set, we could potentially use a QTimer to stop/skip
                # But QMediaPlayer usually handles EndOfMedia correctly.
                # For now, we rely on EndOfMedia or playbackStateChanged to StoppedState.

                logger.debug(
                    f"AudioPlayerManager: Media loaded, now playing. Player state: {self.media_player.playbackState()}")
                if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState and self._is_playing and not self._is_paused:
                    self.media_player.play()  # Ensure it plays if it was supposed to be playing

        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.info(
                f"AudioPlayerManager: EndOfMedia for track '{self.media_player.source().fileName()}'. Advancing.")
            self._advance_to_next_track()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            track_name = "Unknown Track"
            if 0 <= self._current_track_index_in_queue < len(self._track_queue):
                track_name = self._track_queue[self._current_track_index_in_queue]["meta"]["track_name"]
            logger.error(
                f"AudioPlayerManager: Invalid media for track '{track_name}' - {self.media_player.source().path()}")
            self.playback_error_occurred.emit(f"Invalid media: {track_name}")
            self._advance_to_next_track()  # Skip invalid track

    def _handle_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        logger.debug(f"AudioPlayerManager: Playback state changed to {state}")
        if state == QMediaPlayer.PlaybackState.StoppedState:
            # This can happen if a track finishes naturally, or if stop() was called.
            # EndOfMedia is more reliable for natural track end.
            # If _is_playing is true, it implies it wasn't an intentional stop by user.
            if self._is_playing and not self._is_paused and self.media_player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia:
                # If it stopped but wasn't EndOfMedia and wasn't a user pause/stop,
                # it might be an error or unexpected stop.
                # Let's rely on EndOfMedia for advancing primarily.
                # Or if an error occurred, _handle_player_error will manage it.
                pass
        elif state == QMediaPlayer.PlaybackState.PlayingState:
            self._is_playing = True;
            self._is_paused = False
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._is_paused = True;
            self._is_playing = False  # Or keep _is_playing true? Depends on definition

    def _handle_player_error(self, error: QMediaPlayer.Error, error_string: str = ""):
        # error_string from the signal might be empty, use media_player.errorString()
        detailed_error_string = self.media_player.errorString()
        final_error_message = detailed_error_string if detailed_error_string else error_string
        logger.error(
            f"AudioPlayerManager: QMediaPlayer error: {error}, Message: '{final_error_message}' for source {self.media_player.source().fileName()}")
        if error != QMediaPlayer.Error.NoError:
            self.playback_error_occurred.emit(f"Playback error: {final_error_message}")
            # Decide if we should try to advance or stop everything.
            # For now, let's try to advance to the next track.
            self._advance_to_next_track()

    def _advance_to_next_track(self):
        logger.debug("AudioPlayerManager: Advancing to next track.")
        self._current_track_index_in_queue += 1
        if self._current_track_index_in_queue < len(self._track_queue):
            self._play_current_track_in_queue()
        else:  # Reached end of current playlist iteration
            self._handle_program_end()

    def _handle_program_end(self):
        logger.info("AudioPlayerManager: Reached end of current program iteration.")
        if self._loop_indefinitely:
            logger.info("AudioPlayerManager: Looping indefinitely. Restarting program.")
            self._current_track_index_in_queue = 0
            self._play_current_track_in_queue()
        elif self._loop_count_remaining > 0:
            self._loop_count_remaining -= 1
            logger.info(
                f"AudioPlayerManager: Looping. Loops remaining: {self._loop_count_remaining}. Restarting program.")
            self._current_track_index_in_queue = 0
            self._play_current_track_in_queue()
        else:
            logger.info("AudioPlayerManager: Program finished (no more loops).")
            self.stop(emit_finished_signal=True)  # Ensure state is fully stopped and signal emitted

    def pause(self):
        if self._is_playing and not self._is_paused:
            logger.info("AudioPlayerManager: Pausing playback.")
            self.media_player.pause()
            self._is_paused = True
            # self._is_playing remains true, indicating intent to continue
        else:
            logger.debug("AudioPlayerManager: Pause called but not playing or already paused.")

    def resume(self):  # This is essentially what play() does if paused
        self.play()

    def stop(self, emit_finished_signal=False):  # Added param
        logger.info("AudioPlayerManager: Stopping playback.")
        self._is_playing = False
        self._is_paused = False
        # self._next_track_delay_timer.stop()
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()  # This should set position to 0.

        # Reset internal queue state for next fresh play
        self._current_track_index_in_queue = -1

        if emit_finished_signal:
            self.program_playback_finished.emit()

    def set_volume(self, volume_float):  # 0.0 to 1.0
        if 0.0 <= volume_float <= 1.0:
            self.audio_output.setVolume(volume_float)
            logger.debug(f"AudioPlayerManager: Volume set to {volume_float}")
        else:
            logger.warning(f"AudioPlayerManager: Invalid volume {volume_float} requested.")

    def get_total_duration_ms(self) -> int | None:
        """
        Calculates the total effective duration of the currently loaded program.
        Returns None if any track has an unknown duration and no user_end_time.
        This version simply sums effective_duration_ms if available.
        A more robust version might estimate if some are None but others known.
        """
        if not self._track_queue:
            return 0

        total_duration = 0
        for track_info in self._track_queue:
            duration = track_info.get("effective_duration_ms")
            if duration is None:
                # If any track has an indeterminate length based on its metadata and no user_end_ms,
                # the total program duration is also indeterminate.
                # We could try to get player.duration() if only one such track, but that's complex here.
                logger.warning(
                    f"Track '{track_info['meta']['track_name']}' has indeterminate duration; total program duration cannot be calculated accurately.")
                return None
            total_duration += duration

        num_loops = 0
        if self._loop_indefinitely:  # Cannot calculate for indefinite
            logger.info("Cannot calculate total duration for indefinitely looping program.")
            return None
        if self._initial_loop_count > 0:
            num_loops = self._initial_loop_count

        return total_duration * (1 + num_loops) if total_duration is not None else None

    def is_active(self) -> bool:
        return self._is_playing or self._is_paused