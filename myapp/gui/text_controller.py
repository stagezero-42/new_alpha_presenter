# myapp/gui/text_controller.py
import logging
from PySide6.QtCore import QTimer, Signal, QObject
from ..text.paragraph_manager import ParagraphManager
from ..media.media_renderer import MediaRenderer
from ..audio.voice_over_player import VoiceOverPlayer  # NEW
from ..utils.schemas import DEFAULT_VOICE_OVER_VOLUME  # NEW

logger = logging.getLogger(__name__)


class TextController(QObject):
    finished_and_should_advance_slide = Signal()

    def __init__(self, paragraph_manager: ParagraphManager,
                 display_window: MediaRenderer,
                 voice_over_player: VoiceOverPlayer):  # Added voice_over_player
        super().__init__()
        self.paragraph_manager = paragraph_manager
        self.display_window = display_window
        self.voice_over_player = voice_over_player  # NEW: Store VO player instance

        self._paragraph_data = None
        self._current_sentence_index = -1
        self._start_index = -1
        self._end_index = -1

        self._sentence_timing_enabled = False
        self._auto_advance_slide = False
        self._current_text_overlay_settings = {}

        self.sentence_timer = QTimer(self)
        self.sentence_timer.setSingleShot(True)
        self.sentence_timer.timeout.connect(self._handle_sentence_timeout)
        logger.debug("TextController initialized.")

    def is_active(self) -> bool:
        return self._paragraph_data is not None and self._current_sentence_index != -1

    def is_at_start(self) -> bool:
        return self.is_active() and self._current_sentence_index == self._start_index

    def is_at_end(self) -> bool:
        return self.is_active() and self._current_sentence_index == self._end_index

    def stop_sentence_timer(self):
        if self.sentence_timer.isActive():
            logger.debug("Stopping active sentence timer.")
            self.sentence_timer.stop()

    def reset(self):
        logger.debug("Resetting TextController state.")
        self.stop_sentence_timer()
        if self.voice_over_player:  # NEW
            self.voice_over_player.stop()
        self._paragraph_data = None
        self._current_sentence_index = -1
        self._start_index = -1
        self._end_index = -1
        self._sentence_timing_enabled = False
        self._auto_advance_slide = False
        self._current_text_overlay_settings = {}
        if self.display_window:
            self.display_window.clearText()

    def load_slide_text(self, slide_data: dict) -> tuple[bool, int]:
        self.reset()
        text_overlay_settings = slide_data.get("text_overlay")
        if not isinstance(text_overlay_settings, dict) or not text_overlay_settings.get("paragraph_name"):
            logger.debug("No valid text_overlay settings or paragraph_name found in slide_data.")
            return False, 0

        self._current_text_overlay_settings = text_overlay_settings
        self._sentence_timing_enabled = text_overlay_settings.get("sentence_timing_enabled", False)
        self._auto_advance_slide = text_overlay_settings.get("auto_advance_slide", False)
        logger.debug(
            f"TextController loading. Timing: {self._sentence_timing_enabled}, AdvSlide: {self._auto_advance_slide}, Style: {self._current_text_overlay_settings}")
        para_name = self._current_text_overlay_settings.get("paragraph_name")
        start_sent_1based = self._current_text_overlay_settings.get("start_sentence", 1)
        end_sent_spec = self._current_text_overlay_settings.get("end_sentence", 1)
        try:
            self._paragraph_data = self.paragraph_manager.load_paragraph(para_name)
            if not self._paragraph_data: return False, 0
            sentences = self._paragraph_data.get("sentences", [])
            num_para_sentences = len(sentences)
            self._start_index = start_sent_1based - 1
            if isinstance(end_sent_spec, str) and end_sent_spec.lower() == "all":
                self._end_index = num_para_sentences - 1
            elif isinstance(end_sent_spec, int):
                self._end_index = end_sent_spec - 1
            else:
                self.reset(); return False, 0
            if 0 <= self._start_index < num_para_sentences and self._start_index <= self._end_index < num_para_sentences:
                self._current_sentence_index = self._start_index
                initial_delay = slide_data.get("duration", 0)  # This is the slide's initial text delay
                return True, initial_delay
            else:
                logger.error(f"Invalid sentence range for '{para_name}'."); self.reset(); return False, 0
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Error loading paragraph '{para_name}': {e}");
            self.reset();
            return False, 0

    def _display_current_sentence(self):
        if not self.is_active():
            if self.display_window: self.display_window.clearText()
            if self.voice_over_player: self.voice_over_player.stop()  # NEW
            return

        sentences = self._paragraph_data.get("sentences", [])
        if 0 <= self._current_sentence_index < len(sentences):
            sentence_data = sentences[self._current_sentence_index]
            text_to_display = sentence_data.get("text", "")
            logger.info(
                f"Displaying sentence {self._current_sentence_index + 1}/{self._end_index + 1}: '{text_to_display[:30]}...'")
            if self.display_window:
                self.display_window.displayText(text_to_display, self._current_text_overlay_settings)

            # NEW: Play voice-over if available
            if self.voice_over_player:
                self.voice_over_player.stop()  # Stop previous before playing new
                vo_track_name = sentence_data.get("voice_over_track_name")
                if vo_track_name:
                    vo_volume = sentence_data.get("voice_over_volume", DEFAULT_VOICE_OVER_VOLUME)
                    logger.info(f"Playing voice-over: '{vo_track_name}' at volume {vo_volume:.2f}")
                    self.voice_over_player.play(vo_track_name, vo_volume)
        else:
            self.reset()  # Invalid state

    def _start_timer_for_current_sentence(self):
        self.stop_sentence_timer()
        if not self._sentence_timing_enabled or not self.is_active(): return

        sentences = self._paragraph_data.get("sentences", [])
        if 0 <= self._current_sentence_index < len(sentences):
            sentence_data = sentences[self._current_sentence_index]
            delay = sentence_data.get("delay_seconds", 0)  # This delay includes VO duration if set by SentenceManager
            if delay > 0:
                logger.debug(f"Starting sentence timer for {self._current_sentence_index + 1} ({delay}s).")
                self.sentence_timer.start(int(delay * 1000))
            else:  # Delay is 0, if auto_advance_slide is true, it should advance immediately after this sentence
                logger.debug(f"Sentence {self._current_sentence_index + 1} has 0s delay.")
                if self.is_at_end() and self._auto_advance_slide:
                    logger.info("Last sentence (0s delay), auto-advancing slide.")
                    self.finished_and_should_advance_slide.emit()
                elif not self.is_at_end():  # If not last sentence and 0s delay, advance to next sentence immediately
                    QTimer.singleShot(0, lambda: self.show_next_sentence(triggered_by_timer=True))

    def _handle_sentence_timeout(self):
        logger.debug(
            f"Sentence timer timeout. Current sentence: {self._current_sentence_index + 1}, End: {self._end_index + 1}")
        if not self.is_active(): return
        if self.voice_over_player: self.voice_over_player.stop()  # Stop VO for current sentence

        if self.is_at_end():
            if self._auto_advance_slide:
                logger.info("Last sentence timer ended, auto-advancing slide.")
                self.finished_and_should_advance_slide.emit()
            else:
                logger.info("Last sentence timer ended, no slide advance.")
        else:
            self.show_next_sentence(triggered_by_timer=True)

    def show_first_sentence(self):
        if self._paragraph_data and self._start_index != -1:
            logger.debug("TextController: Showing first sentence.")
            if self.voice_over_player: self.voice_over_player.stop()  # Stop any prior
            self._current_sentence_index = self._start_index
            self._display_current_sentence()  # This will also trigger its VO if any
            self._start_timer_for_current_sentence()
        else:
            logger.warning("show_first_sentence called but no text loaded correctly.")

    def show_next_sentence(self, triggered_by_timer=False) -> bool:
        if not triggered_by_timer: self.stop_sentence_timer()
        if self.voice_over_player: self.voice_over_player.stop()  # NEW: Stop VO of previous sentence

        if not self.is_active() or self.is_at_end(): return False
        self._current_sentence_index += 1
        self._display_current_sentence()  # This will also trigger its VO if any
        if self._sentence_timing_enabled: self._start_timer_for_current_sentence()
        return True

    def show_prev_sentence(self) -> bool:
        self.stop_sentence_timer()
        if self.voice_over_player: self.voice_over_player.stop()  # NEW: Stop VO of current sentence

        if not self.is_active() or self.is_at_start(): return False
        self._current_sentence_index -= 1
        self._display_current_sentence()  # This will also trigger its VO if any
        # When going previous, typically timing is interrupted.
        # if self._sentence_timing_enabled: self._start_timer_for_current_sentence()
        return True