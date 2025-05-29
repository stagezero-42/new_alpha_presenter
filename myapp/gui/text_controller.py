# myapp/gui/text_controller.py
import logging
from PySide6.QtCore import QTimer, Signal, QObject # Added QTimer, Signal, QObject
from ..text.paragraph_manager import ParagraphManager
from ..media.media_renderer import MediaRenderer

logger = logging.getLogger(__name__)

class TextController(QObject): # Inherit from QObject for signals
    """
    Manages the state and display of text overlays for a slide, including timed progression.
    """
    # Signal emitted when text finishes and auto-advance to next slide is enabled
    finished_and_should_advance_slide = Signal()

    def __init__(self, paragraph_manager: ParagraphManager, display_window: MediaRenderer):
        super().__init__() # Call QObject constructor
        self.paragraph_manager = paragraph_manager
        self.display_window = display_window
        self._paragraph_data = None
        self._current_sentence_index = -1
        self._start_index = -1
        self._end_index = -1

        self._sentence_timing_enabled = False
        self._auto_advance_slide = False

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
        if self.display_window:
            self.display_window.clearText()

    def load_slide_text(self, slide_data: dict, sentence_timing_enabled: bool, auto_advance_slide: bool) -> tuple[bool, int]:
        self.reset()
        self._sentence_timing_enabled = sentence_timing_enabled
        self._auto_advance_slide = auto_advance_slide
        logger.debug(f"TextController loading slide. Timing enabled: {self._sentence_timing_enabled}, Advance slide: {self._auto_advance_slide}")

        text_overlay_info = slide_data.get("text_overlay")
        if not text_overlay_info: return False, 0

        para_name = text_overlay_info.get("paragraph_name")
        start_sent_1based = text_overlay_info.get("start_sentence")
        end_sent_spec = text_overlay_info.get("end_sentence")

        if not (para_name and start_sent_1based is not None and end_sent_spec is not None):
            logger.warning("Incomplete text_overlay data.")
            return False, 0

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

            if 0 <= self._start_index < num_para_sentences and \
               self._start_index <= self._end_index < num_para_sentences:
                self._current_sentence_index = self._start_index # Set for show_first_sentence
                initial_delay = slide_data.get("duration", 0) # This is the pre-text delay
                return True, initial_delay
            else:
                logger.error(f"Invalid sentence range for '{para_name}'.")
                self.reset(); return False, 0
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Error loading paragraph '{para_name}': {e}")
            self.reset(); return False, 0

    def _display_current_sentence(self):
        if not self.is_active():
            if self.display_window: self.display_window.clearText()
            return

        sentences = self._paragraph_data.get("sentences", [])
        if 0 <= self._current_sentence_index < len(sentences):
            sentence_data = sentences[self._current_sentence_index]
            text = sentence_data.get("text", "")
            logger.info(f"Displaying sentence {self._current_sentence_index + 1}/{self._end_index +1}: '{text}'")
            if self.display_window: self.display_window.displayText(text)
        else:
            self.reset()

    def _start_timer_for_current_sentence(self):
        self.stop_sentence_timer() # Stop any existing timer
        if not self._sentence_timing_enabled or not self.is_active():
            return

        sentences = self._paragraph_data.get("sentences", [])
        if 0 <= self._current_sentence_index < len(sentences):
            sentence_data = sentences[self._current_sentence_index]
            delay = sentence_data.get("delay_seconds", 0) # Default to 0 if not specified
            if delay > 0:
                logger.debug(f"Starting timer for sentence {self._current_sentence_index + 1} ({delay}s).")
                self.sentence_timer.start(int(delay * 1000))
            else:
                logger.debug(f"Sentence {self._current_sentence_index + 1} has 0s delay, no timer started.")
        else:
            logger.warning("Tried to start timer for invalid sentence index.")


    def _handle_sentence_timeout(self):
        logger.debug(f"Sentence timer timeout. Current sentence: {self._current_sentence_index + 1}, End: {self._end_index + 1}")
        if not self.is_active(): return # Should not happen if timer was active

        if self.is_at_end():
            if self._auto_advance_slide:
                logger.info("Last sentence timer ended, auto-advancing slide.")
                self.finished_and_should_advance_slide.emit()
            else:
                logger.info("Last sentence timer ended, no slide advance.")
                # Text stays on the last sentence
        else:
            self.show_next_sentence(triggered_by_timer=True) # Internal call, will start next timer

    def show_first_sentence(self):
        """Sets the index to the start, displays it, and starts its timer if enabled."""
        if self._paragraph_data and self._start_index != -1:
            logger.debug("TextController: Showing first sentence.")
            self._current_sentence_index = self._start_index
            self._display_current_sentence()
            self._start_timer_for_current_sentence() # Start timer for this first sentence
        else:
            logger.warning("show_first_sentence called but no text loaded correctly.")

    def show_next_sentence(self, triggered_by_timer=False) -> bool:
        """Advances to and displays the next sentence. Starts timer if enabled."""
        if not triggered_by_timer: # Manual advancement
            self.stop_sentence_timer()

        if not self.is_active() or self.is_at_end():
            return False

        self._current_sentence_index += 1
        self._display_current_sentence()
        if not triggered_by_timer: # Only start new timer if manually advanced here
             self._start_timer_for_current_sentence()
        elif self._sentence_timing_enabled: # If triggered by timer, next sentence also gets its timer
             self._start_timer_for_current_sentence()
        return True

    def show_prev_sentence(self) -> bool:
        """Goes to and displays the previous sentence. Stops current sentence timer."""
        self.stop_sentence_timer() # Manual navigation stops current timer

        if not self.is_active() or self.is_at_start():
            return False

        self._current_sentence_index -= 1
        self._display_current_sentence()
        # Optionally, you could restart the timer for the previous sentence if _sentence_timing_enabled
        # For now, let's assume 'prev' always goes to manual mode for that sentence.
        # self._start_timer_for_current_sentence()
        return True