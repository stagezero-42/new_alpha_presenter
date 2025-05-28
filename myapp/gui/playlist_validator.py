# myapp/gui/playlist_validator.py
import logging
from ..text.paragraph_manager import ParagraphManager
from ..playlist.playlist import Playlist

logger = logging.getLogger(__name__)

class PlaylistValidator:
    """
    Validates a Playlist object to find potential issues or inconsistencies.
    """

    def __init__(self, paragraph_manager: ParagraphManager):
        """
        Initializes the PlaylistValidator.

        Args:
            paragraph_manager: An instance of ParagraphManager to load text data.
        """
        if not paragraph_manager:
            raise ValueError("ParagraphManager instance is required.")
        self.paragraph_manager = paragraph_manager
        logger.debug("PlaylistValidator initialized.")

    def validate(self, playlist: Playlist) -> list:
        """
        Validates the entire playlist and returns a list of found issues.

        Args:
            playlist: The Playlist object to validate.

        Returns:
            A list of dictionaries, where each dictionary represents a slide with issues.
            Format: [{'index': int, 'icons': set(), 'descriptions': list}, ...]
            Returns an empty list if no issues are found.
        """
        logger.debug("Starting playlist validation...")
        if not playlist or not playlist.get_slides():
            logger.debug("Playlist is empty, no validation needed.")
            return []

        issues_found = []
        slides = playlist.get_slides()
        num_slides = len(slides)

        for i, slide_data in enumerate(slides):
            slide_issues = {"index": i, "icons": set(), "descriptions": []}
            duration = slide_data.get("duration", 0)
            loop_target = slide_data.get("loop_to_slide", 0)  # 1-based
            text_overlay = slide_data.get("text_overlay")

            # 1. Timer Useless Check
            if i == num_slides - 1 and duration > 0 and not text_overlay:
                if loop_target == 0 or loop_target == (i + 1):
                    slide_issues["icons"].add("timer")
                    slide_issues["descriptions"].append("Useless Timer (last slide)")

            # 2. Loop Inactive Check
            if loop_target > 0 and duration == 0:
                slide_issues["icons"].add("loop")
                slide_issues["descriptions"].append("Inactive Loop (0s duration/delay)")

            # 3. Self Loop Check
            if loop_target == (i + 1) and num_slides > 1:
                is_last_slide_self_loop = (i == num_slides - 1) and (loop_target == i + 1)
                if not (is_last_slide_self_loop and duration > 0 and not text_overlay):
                    slide_issues["icons"].add("loop")
                    slide_issues["descriptions"].append("Self Loop")

            # 4. Text Issues Check
            if text_overlay:
                self._validate_text_overlay(text_overlay, slide_issues)

            if slide_issues["icons"]:
                issues_found.append(slide_issues)

        logger.info(f"Playlist validation finished. Found {len(issues_found)} slides with issues.")
        return issues_found

    def _validate_text_overlay(self, text_overlay: dict, slide_issues: dict):
        """Validates the text_overlay part of a slide."""
        para_name = text_overlay.get("paragraph_name")
        start_sent_1based = text_overlay.get("start_sentence")
        end_sent_spec = text_overlay.get("end_sentence")

        if not para_name:
            slide_issues["icons"].add("text")
            slide_issues["descriptions"].append("Text Missing (No paragraph name)")
            return # No point checking range if no name

        try:
            para_data = self.paragraph_manager.load_paragraph(para_name)
            if not para_data:
                slide_issues["icons"].add("text")
                slide_issues["descriptions"].append("Text Missing (Not found)")
                return

            num_para_sentences = len(para_data.get("sentences", []))
            if num_para_sentences == 0:
                 slide_issues["icons"].add("text")
                 slide_issues["descriptions"].append("Text Error (Paragraph empty)")
                 return

            start_idx_0based = start_sent_1based - 1 if isinstance(start_sent_1based, int) else -1

            end_idx_0based = -1
            if isinstance(end_sent_spec, str) and end_sent_spec.lower() == "all":
                end_idx_0based = num_para_sentences - 1
            elif isinstance(end_sent_spec, int):
                end_idx_0based = end_sent_spec - 1

            # Check range validity
            if not (0 <= start_idx_0based < num_para_sentences and \
                    start_idx_0based <= end_idx_0based < num_para_sentences):
                slide_issues["icons"].add("text")
                slide_issues["descriptions"].append("Text Range Invalid")

        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Error loading paragraph '{para_name}' during validation: {e}")
            slide_issues["icons"].add("text")
            slide_issues["descriptions"].append("Text Missing (Load error)")
        except Exception as e:
            logger.error(f"Unexpected error validating text for '{para_name}': {e}", exc_info=True)
            slide_issues["icons"].add("text")
            slide_issues["descriptions"].append("Text Error (Unexpected)")