# myapp/audio/voice_over_player.py
import os
import logging
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_media_file_path
from ..utils.schemas import DEFAULT_VOICE_OVER_VOLUME

logger = logging.getLogger(__name__)

class VoiceOverPlayer(QObject):
    playback_error_occurred = Signal(str)
    playback_finished = Signal()

    def __init__(self, track_manager: AudioTrackManager, parent=None):
        super().__init__(parent)
        self.track_manager = track_manager

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.set_volume(DEFAULT_VOICE_OVER_VOLUME)

        self.current_track_name = None
        self.current_source_path = None # Keep track of what source was set
        self.is_playing = False

        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)

        logger.debug("VoiceOverPlayer initialized.")

    def play(self, track_metadata_name: str, volume: float = None, start_time_ms: int = 0):
        logger.info(f"VoiceOverPlayer: Play requested for track '{track_metadata_name}', volume: {volume}, start_ms: {start_time_ms}")
        # Stop any current playback first, ensure source is cleared if player was active
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
        if not self.media_player.source().isEmpty(): # Explicitly clear source
             self.media_player.setSource(QUrl())

        self.is_playing = False # Reset playing state until media is loaded
        self.current_track_name = None # Reset current track name until successfully loaded
        self.current_source_path = None

        if not track_metadata_name:
            logger.warning("VoiceOverPlayer: No track name provided to play.")
            return

        try:
            track_metadata = self.track_manager.load_track_metadata(track_metadata_name)
            if not track_metadata or not track_metadata.get("file_path"):
                msg = f"Metadata or file_path missing for voice-over track '{track_metadata_name}'."
                logger.warning(msg)
                self.playback_error_occurred.emit(msg)
                return

            media_content_path = get_media_file_path(track_metadata["file_path"])
            if not os.path.exists(media_content_path):
                msg = f"Audio file not found for voice-over: {media_content_path}."
                logger.error(msg)
                self.playback_error_occurred.emit(msg)
                return

            self.current_track_name = track_metadata_name # Tentatively set
            self.current_source_path = media_content_path # Store expected path
            if volume is not None:
                self.set_volume(volume)

            self.media_player.setSource(QUrl.fromLocalFile(media_content_path))
            # Playback will start on LoadedMedia status

        except Exception as e:
            msg = f"Error loading voice-over track '{track_metadata_name}': {e}"
            logger.error(msg, exc_info=True)
            self.playback_error_occurred.emit(msg)
            self.current_track_name = None
            self.current_source_path = None

    def stop(self):
        track_before_stop = self.current_track_name
        if self.is_playing or self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            logger.debug(f"VoiceOverPlayer: Stopping playback of '{track_before_stop}'.")
            self.media_player.stop() # This should set state to StoppedState
        if not self.media_player.source().isEmpty(): # Explicitly clear source after stopping
             self.media_player.setSource(QUrl())
             logger.debug(f"VoiceOverPlayer: Source cleared for '{track_before_stop}'.")

        self.is_playing = False
        self.current_track_name = None
        self.current_source_path = None


    def set_volume(self, volume_float: float):
        if 0.0 <= volume_float <= 1.0:
            self.audio_output.setVolume(volume_float)
            logger.debug(f"VoiceOverPlayer: Volume set to {volume_float:.2f}")
        else:
            logger.warning(f"VoiceOverPlayer: Invalid volume {volume_float} requested.")

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        player_source_file = os.path.basename(self.media_player.source().toLocalFile())
        logger.debug(f"VoiceOverPlayer: MediaStatusChanged for source '{player_source_file}' (expected: '{os.path.basename(str(self.current_source_path))}'): {status}")

        if self.media_player.source().isEmpty() or not self.current_track_name or not self.current_source_path:
            if status == QMediaPlayer.MediaStatus.LoadedMedia and self.media_player.source().isEmpty():
                logger.debug("VoiceOverPlayer: Media loaded for an empty source. Ignoring.")
            elif status != QMediaPlayer.MediaStatus.NoMedia : # Avoid logging NoMedia for already cleared source
                logger.debug("VoiceOverPlayer: Media status changed but no current track context or source is empty. Ignoring.")
            return

        # Ensure the status change is for the track we intend to play
        if os.path.normpath(self.media_player.source().toLocalFile()) != os.path.normpath(self.current_source_path):
            logger.warning(f"VoiceOverPlayer: Media status {status} for '{player_source_file}' does not match expected track '{os.path.basename(str(self.current_source_path))}'. Ignoring.")
            return

        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            logger.info(f"VoiceOverPlayer: Media loaded for '{self.current_track_name}'. Starting play.")
            self.media_player.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.info(f"VoiceOverPlayer: EndOfMedia for '{self.current_track_name}'.")
            self.is_playing = False # Update state before emitting
            finished_track = self.current_track_name
            self.current_track_name = None
            self.current_source_path = None
            self.playback_finished.emit()
            logger.debug(f"VoiceOverPlayer: Emitted playback_finished for {finished_track}")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            msg = f"Invalid media for voice-over track '{self.current_track_name}'."
            logger.error(msg)
            self.playback_error_occurred.emit(msg)
            self.is_playing = False
            self.current_track_name = None
            self.current_source_path = None

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        logger.debug(f"VoiceOverPlayer: PlaybackStateChanged for '{self.current_track_name}': {state}")
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.is_playing = True
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.is_playing = False
            # If stopped and not due to EndOfMedia, it might be an error or explicit stop.
            # Error is handled by _on_player_error. Explicit stop clears current_track_name.
            # If current_track_name is still set here, it means an unexpected stop.
            if self.current_track_name and self.media_player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia:
                logger.warning(f"VoiceOverPlayer: Playback for '{self.current_track_name}' stopped unexpectedly (not EndOfMedia).")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.is_playing = False

    def _on_player_error(self, error_enum):
        # Use self.current_track_name if available, otherwise the source from the player
        track_context = self.current_track_name or os.path.basename(self.media_player.source().toLocalFile())
        error_string = self.media_player.errorString()
        final_error_message = error_string if error_string else f"Unknown player error ({error_enum})"
        logger.error(f"VoiceOverPlayer QMediaPlayer Error for '{track_context}': {error_enum}, String: '{final_error_message}'")

        if error_enum != QMediaPlayer.Error.NoError:
            self.playback_error_occurred.emit(f"Playback error on '{track_context}': {final_error_message}")

        self.is_playing = False
        self.current_track_name = None # Clear context on error
        self.current_source_path = None