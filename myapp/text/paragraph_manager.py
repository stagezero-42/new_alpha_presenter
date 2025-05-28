# myapp/text/paragraph_manager.py
import os
import json
import logging
from ..utils.paths import get_texts_path # Still need this for default
from ..utils.schemas import PARAGRAPH_SCHEMA
from ..utils.json_validator import validate_json
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)

class ParagraphManager:
    """Manages loading, saving, and listing Paragraph JSON files."""

    # --- MODIFIED: Accept optional texts_dir ---
    def __init__(self, texts_dir=None):
        """
        Initializes the ParagraphManager.

        Args:
            texts_dir (str, optional): The path to the texts directory.
                                       If None, uses get_texts_path().
        """
        self.texts_dir = texts_dir if texts_dir is not None else get_texts_path()
    # --- END MODIFIED ---
        os.makedirs(self.texts_dir, exist_ok=True)
        logger.debug(f"ParagraphManager initialized. Text directory: {self.texts_dir}")

    # --- NEW: Internal helper to use self.texts_dir ---
    def _get_file_path(self, paragraph_name):
        """Constructs the full path for a paragraph file."""
        return os.path.join(self.texts_dir, f"{paragraph_name}.json")
    # --- END NEW ---

    def load_paragraph(self, paragraph_name):
        """
        Loads a single paragraph from its JSON file.
        """
        if not is_safe_filename_component(f"{paragraph_name}.json"):
            logger.error(f"Attempted to load paragraph with unsafe name: {paragraph_name}")
            return None

        # --- MODIFIED: Use internal helper ---
        file_path = self._get_file_path(paragraph_name)
        # --- END MODIFIED ---
        logger.info(f"Loading paragraph: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"Paragraph file not found: {file_path}")
            raise FileNotFoundError(f"Paragraph file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            is_valid, error = validate_json(data, PARAGRAPH_SCHEMA, f"Paragraph '{paragraph_name}'")
            if not is_valid:
                logger.error(f"Paragraph file '{paragraph_name}' has invalid format: {error.message if error else 'Unknown validation error'}")
                raise ValueError(f"Paragraph file has invalid format: {error.message if error else 'Unknown'}")

            if data.get("name") != paragraph_name:
                 logger.warning(f"Paragraph name '{data.get('name')}' in file does not match filename '{paragraph_name}'. Using filename.")
                 data["name"] = paragraph_name

            logger.info(f"Successfully loaded paragraph: {paragraph_name}")
            return data

        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.error(f"Failed to load or parse paragraph: {file_path}\n{e}", exc_info=True)
            raise ValueError(f"Failed to load or parse paragraph: {file_path}\n{e}")

    def save_paragraph(self, paragraph_name, data):
        """
        Saves a single paragraph to its JSON file.
        """
        if not is_safe_filename_component(f"{paragraph_name}.json"):
            logger.error(f"Attempted to save paragraph with unsafe name: {paragraph_name}")
            return False

        # --- MODIFIED: Use internal helper ---
        file_path = self._get_file_path(paragraph_name)
        # --- END MODIFIED ---
        logger.info(f"Saving paragraph to: {file_path}")

        if data.get("name") != paragraph_name:
            logger.warning(f"Data name '{data.get('name')}' differs from save name '{paragraph_name}'. Saving with '{paragraph_name}'.")
            data["name"] = paragraph_name

        is_valid, error = validate_json(data, PARAGRAPH_SCHEMA, f"Paragraph data for '{paragraph_name}'")
        if not is_valid:
            logger.error(f"Cannot save paragraph '{paragraph_name}', data invalid: {error.message if error else 'Unknown'}")
            return False

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Paragraph '{paragraph_name}' saved successfully.")
            return True
        except IOError as e:
            logger.error(f"Error saving paragraph to {file_path}: {e}", exc_info=True)
            return False

    def list_paragraphs(self):
        """
        Lists all available paragraph names in the texts directory.
        """
        try:
            files = [f for f in os.listdir(self.texts_dir)
                     if os.path.isfile(os.path.join(self.texts_dir, f)) and f.lower().endswith('.json')]
            names = [os.path.splitext(f)[0] for f in files]
            logger.debug(f"Found paragraphs: {names}")
            return names
        except OSError as e:
            logger.error(f"Error listing paragraphs in {self.texts_dir}: {e}", exc_info=True)
            return []

    def delete_paragraph(self, paragraph_name):
        """
        Deletes a paragraph file.
        """
        if not is_safe_filename_component(f"{paragraph_name}.json"):
            logger.error(f"Attempted to delete paragraph with unsafe name: {paragraph_name}")
            return False

        # --- MODIFIED: Use internal helper ---
        file_path = self._get_file_path(paragraph_name)
        # --- END MODIFIED ---
        logger.warning(f"Attempting to delete paragraph: {file_path}")
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Paragraph '{paragraph_name}' deleted.")
            else:
                logger.info(f"Paragraph '{paragraph_name}' did not exist, nothing to delete.")
            return True
        except OSError as e:
            logger.error(f"Error deleting paragraph {file_path}: {e}", exc_info=True)
            return False