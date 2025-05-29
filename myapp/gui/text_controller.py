# myapp/gui/text_controller.py
import logging
from PySide6.QtCore import QTimer, Signal, QObject
from ..text.paragraph_manager import ParagraphManager
from ..media.media_renderer import MediaRenderer  # Ensure this import is correct

logger = logging.getLogger(__name__)


class TextController(QObject):
    finished_and_should_advance_slide = Signal()

    def __init__(self, paragraph_manager: ParagraphManager, display_window: MediaRenderer):
        super().__init__()
        self.paragraph_manager = paragraph_manager
        self.display_window = display_window  # MediaRenderer instance
        self._paragraph_data = None
        self._current_sentence_index = -1
        self._start_index = -1
        self._end_index = -1

        self._sentence_timing_enabled = False
        self._auto_advance_slide = False
        self._current_text_overlay_settings = {}  # To store all settings including style

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
        self._paragraph_data = None
        self._current_sentence_index = -1
        self._start_index = -1
        self._end_index = -1
        self._sentence_timing_enabled = False
        self._auto_advance_slide = False
        self._current_text_overlay_settings = {}  # Clear stored settings
        if self.display_window:
            self.display_window.clearText()  # MediaRenderer's method to clear text

    def load_slide_text(self, slide_data: dict,
                        # sentence_timing_enabled and auto_advance_slide are now part of text_overlay_settings
                        ) -> tuple[bool, int]:  # Returns (can_show_text, initial_delay_for_slide_timer)
        self.reset()

        text_overlay_settings = slide_data.get("text_overlay")
        if not isinstance(text_overlay_settings, dict) or not text_overlay_settings.get("paragraph_name"):
            logger.debug("No valid text_overlay settings or paragraph_name found in slide_data.")
            return False, 0

        self._current_text_overlay_settings = text_overlay_settings  # Store all settings
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
                self.reset();
                return False, 0

            if 0 <= self._start_index < num_para_sentences and \
                    self._start_index <= self._end_index < num_para_sentences:
                self._current_sentence_index = self._start_index
                initial_delay = slide_data.get("duration", 0)
                return True, initial_delay
            else:
                logger.error(f"Invalid sentence range for '{para_name}'.")
                self.reset();
                return False, 0
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Error loading paragraph '{para_name}': {e}")
            self.reset();
            return False, 0

    def _display_current_sentence(self):
        if not self.is_active():
            if self.display_window: self.display_window.clearText()
            return

        sentences = self._paragraph_data.get("sentences", [])
        if 0 <= self._current_sentence_index < len(sentences):
            sentence_data = sentences[self._current_sentence_index]
            text = sentence_data.get("text", "")
            logger.info(
                f"Displaying sentence {self._current_sentence_index + 1}/{self._end_index + 1}: '{text[:30]}...'")
            if self.display_window:
                # Pass the stored full text_overlay_settings which include style
                self.display_window.displayText(text, self._current_text_overlay_settings)
        else:
            self.reset()

    def _start_timer_for_current_sentence(self):
        self.stop_sentence_timer()
        if not self._sentence_timing_enabled or not self.is_active():
            return

        sentences = self._paragraph_data.get("sentences", [])
        if 0 <= self._current_sentence_index < len(sentences):
            sentence_data = sentences[self._current_sentence_index]
            delay = sentence_data.get("delay_seconds", 0)
            if delay > 0:
                logger.debug(f"Starting timer for sentence {self._current_sentence_index + 1} ({delay}s).")
                self.sentence_timer.start(int(delay * 1000))
            else:  # If delay is 0, and timing is on, treat as manual for this sentence? Or advance immediately?
                # For now, 0 delay means it waits for manual or next timeout from a previous non-zero delay sentence.
                # Or, if _handle_sentence_timeout calls show_next_sentence, a 0-delay here would rapidly fire.
                # Let's assume 0-delay means it shows and waits.
                logger.debug(
                    f"Sentence {self._current_sentence_index + 1} has 0s delay, timer not started by _start_timer_for_current_sentence.")
        else:
            logger.warning("Tried to start timer for invalid sentence index.")

    def _handle_sentence_timeout(self):
        logger.debug(
            f"Sentence timer timeout. Current sentence: {self._current_sentence_index + 1}, End: {self._end_index + 1}")
        if not self.is_active(): return

        if self.is_at_end():
            if self._auto_advance_slide:
                logger.info("Last sentence timer ended, auto-advancing slide.")
                self.finished_and_should_advance_slide.emit()
            else:
                logger.info("Last sentence timer ended, no slide advance.")
        else:
            # Advance to the next sentence and it will start its own timer
            self.show_next_sentence(triggered_by_timer=True)

    def show_first_sentence(self):
        if self._paragraph_data and self._start_index != -1:
            logger.debug("TextController: Showing first sentence.")
            self._current_sentence_index = self._start_index
            self._display_current_sentence()
            self._start_timer_for_current_sentence()
        else:
            logger.warning("show_first_sentence called but no text loaded correctly.")

    def show_next_sentence(self, triggered_by_timer=False) -> bool:
        if not triggered_by_timer:
            self.stop_sentence_timer()

        if not self.is_active() or self.is_at_end():
            return False

        self._current_sentence_index += 1
        self._display_current_sentence()
        # Start timer for this new sentence, regardless of how we got here (manual or timer)
        # if sentence timing is enabled.
        if self._sentence_timing_enabled:
            self._start_timer_for_current_sentence()
        return True

    def show_prev_sentence(self) -> bool:
        self.stop_sentence_timer()

        if not self.is_active() or self.is_at_start():
            return False

        self._current_sentence_index -= 1
        self._display_current_sentence()
        # When going previous, typically timing is interrupted and becomes manual.
        # If you want previous to also restart timing for the now current (previous) sentence:
        # if self._sentence_timing_enabled:
        #    self._start_timer_for_current_sentence()
        return True