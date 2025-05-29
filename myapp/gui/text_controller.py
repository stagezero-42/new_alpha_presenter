# myapp/gui/text_controller.py
import logging
from ..text.paragraph_manager import ParagraphManager
from ..media.media_renderer import MediaRenderer

logger = logging.getLogger(__name__)

class TextController:
    """
    Manages the state and display of text overlays for a slide.
    """

    def __init__(self, paragraph_manager: ParagraphManager, display_window: MediaRenderer):
        """
        Initializes the TextController.

        Args:
            paragraph_manager: An instance for loading text data.
            display_window: The window where text will be rendered.
        """
        self.paragraph_manager = paragraph_manager
        self.display_window = display_window
        self._paragraph_data = None
        self._current_sentence_index = -1
        self._start_index = -1
        self._end_index = -1
        logger.debug("TextController initialized.")

    def is_active(self) -> bool:
        """Checks if a text overlay is currently loaded and active."""
        return self._paragraph_data is not None and self._current_sentence_index != -1

    def is_at_start(self) -> bool:
        """Checks if the currently displayed sentence is the first one for the slide."""
        return self.is_active() and self._current_sentence_index == self._start_index

    def is_at_end(self) -> bool:
        """Checks if the currently displayed sentence is the last one for the slide."""
        return self.is_active() and self._current_sentence_index == self._end_index

    def reset(self):
        """Resets the text state and clears text from the display."""
        logger.debug("Resetting TextController state.")
        self._paragraph_data = None
        self._current_sentence_index = -1
        self._start_index = -1
        self._end_index = -1
        if self.display_window:
            self.display_window.clearText()

    def load_slide_text(self, slide_data: dict) -> tuple[bool, int]:
        """
        Attempts to load text data for a given slide.

        Args:
            slide_data: The dictionary representing the slide.

        Returns:
            A tuple (bool, int):
            - True if text can be displayed, False otherwise.
            - The initial delay in seconds if text can be displayed, 0 otherwise.
            Returns (False, 0) on any error or if no text overlay is defined.
        """
        self.reset()
        text_overlay_info = slide_data.get("text_overlay")

        if not text_overlay_info:
            return False, 0

        para_name = text_overlay_info.get("paragraph_name")
        start_sent_1based = text_overlay_info.get("start_sentence")
        end_sent = text_overlay_info.get("end_sentence")

        if not (para_name and start_sent_1based is not None and end_sent is not None):
            logger.warning(f"Slide has incomplete text_overlay data. No text shown.")
            return False, 0

        try:
            self._paragraph_data = self.paragraph_manager.load_paragraph(para_name)
            if not self._paragraph_data:
                logger.error(f"Failed to load paragraph '{para_name}' (returned None). No text shown.")
                return False, 0

            sentences = self._paragraph_data.get("sentences", [])
            num_para_sentences = len(sentences)
            self._start_index = start_sent_1based - 1

            if isinstance(end_sent, str) and end_sent.lower() == "all":
                self._end_index = num_para_sentences - 1
            elif isinstance(end_sent, int):
                self._end_index = end_sent - 1
            else:
                logger.error(f"Invalid end_sentence format: {end_sent}. No text shown.")
                self.reset()
                return False, 0

            if 0 <= self._start_index < num_para_sentences and \
               self._start_index <= self._end_index < num_para_sentences:
                # Valid range, text can be shown
                self._current_sentence_index = self._start_index
                initial_delay = slide_data.get("duration", 0)
                logger.info(f"Text loaded for '{para_name}' (Sentences {self._start_index + 1} to {self._end_index + 1}). Delay: {initial_delay}s.")
                return True, initial_delay
            else:
                logger.error(f"Invalid sentence range (0-based: {self._start_index}-{self._end_index}) for '{para_name}' ({num_para_sentences} sentences). No text shown.")
                self.reset()
                return False, 0

        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Error loading paragraph '{para_name}': {e}", exc_info=True)
            self.reset()
            return False, 0 # Indicate error by returning False

    def _display_current_sentence(self):
        """Internal helper to display the sentence at _current_sentence_index."""
        if not self.is_active():
            logger.debug("_display_current_sentence called but not active.")
            if self.display_window: self.display_window.clearText()
            return

        sentences = self._paragraph_data.get("sentences", [])
        if 0 <= self._current_sentence_index < len(sentences):
            sentence_data = sentences[self._current_sentence_index]
            text = sentence_data.get("text", "")
            logger.info(f"Displaying sentence {self._current_sentence_index + 1}: '{text}'")
            if self.display_window:
                self.display_window.displayText(text)
        else:
            logger.error(f"Sentence index {self._current_sentence_index} out of bounds. Resetting.")
            self.reset()

    def show_first_sentence(self):
        """Sets the index to the start and displays the first sentence."""
        if self._paragraph_data and self._start_index != -1:
            logger.debug("Showing first sentence.")
            self._current_sentence_index = self._start_index
            self._display_current_sentence()
        else:
            logger.warning("show_first_sentence called but no text loaded.")

    def show_next_sentence(self) -> bool:
        """Advances to the next sentence and displays it. Returns False if at the end."""
        if not self.is_active() or self.is_at_end():
            return False

        self._current_sentence_index += 1
        self._display_current_sentence()
        return True

    def show_prev_sentence(self) -> bool:
        """Goes to the previous sentence and displays it. Returns False if at the start."""
        if not self.is_active() or self.is_at_start():
            return False

        self._current_sentence_index -= 1
        self._display_current_sentence()
        return True