# myapp/audio/audio_program_manager.py
import os
import json
import logging
from ..utils.paths import get_audio_programs_path
from ..utils.schemas import AUDIO_PROGRAM_SCHEMA
from ..utils.json_validator import validate_json
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)

class AudioProgramManager:
    """Manages loading, saving, and listing Audio Program JSON files."""

    def __init__(self, audio_programs_dir=None):
        self.audio_programs_dir = audio_programs_dir if audio_programs_dir is not None else get_audio_programs_path()
        os.makedirs(self.audio_programs_dir, exist_ok=True)
        logger.debug(f"AudioProgramManager initialized. Program directory: {self.audio_programs_dir}")

    def _get_program_file_path(self, program_name):
        return os.path.join(self.audio_programs_dir, f"{program_name}.json")

    def load_program(self, program_name):
        if not is_safe_filename_component(f"{program_name}.json"):
            logger.error(f"Attempted to load audio program with unsafe name: {program_name}")
            return None

        file_path = self._get_program_file_path(program_name)
        logger.info(f"Loading audio program: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"Audio program file not found: {file_path}")
            raise FileNotFoundError(f"Audio program file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            is_valid, error = validate_json(data, AUDIO_PROGRAM_SCHEMA, f"Audio Program '{program_name}'")
            if not is_valid:
                msg = error.message if error else 'Unknown validation error'
                logger.error(f"Audio program file '{program_name}' has invalid format: {msg}")
                raise ValueError(f"Audio program file has invalid format: {msg}")

            if data.get("program_name") != program_name:
                logger.warning(f"Program name '{data.get('program_name')}' in file does not match filename '{program_name}'. Using filename.")
                data["program_name"] = program_name

            logger.info(f"Successfully loaded audio program: {program_name}")
            return data
        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.error(f"Failed to load or parse audio program: {file_path}\n{e}", exc_info=True)
            raise ValueError(f"Failed to load or parse audio program: {file_path}\n{e}")

    def save_program(self, program_name, data):
        if not is_safe_filename_component(f"{program_name}.json"):
            logger.error(f"Attempted to save audio program with unsafe name: {program_name}")
            return False

        file_path = self._get_program_file_path(program_name)
        logger.info(f"Saving audio program to: {file_path}")

        if data.get("program_name") != program_name:
            logger.warning(f"Data program_name '{data.get('program_name')}' differs from save name '{program_name}'. Saving with '{program_name}'.")
            data["program_name"] = program_name

        is_valid, error = validate_json(data, AUDIO_PROGRAM_SCHEMA, f"Audio Program data for '{program_name}'")
        if not is_valid:
            msg = error.message if error else 'Unknown validation error'
            logger.error(f"Cannot save audio program '{program_name}', data invalid: {msg}")
            return False

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Audio program '{program_name}' saved successfully.")
            return True
        except IOError as e:
            logger.error(f"Error saving audio program to {file_path}: {e}", exc_info=True)
            return False

    def list_programs(self):
        """Lists all available audio program names."""
        try:
            files = [f for f in os.listdir(self.audio_programs_dir)
                     if os.path.isfile(os.path.join(self.audio_programs_dir, f)) and f.lower().endswith('.json')]
            names = [os.path.splitext(f)[0] for f in files]
            logger.debug(f"Found audio programs: {names}")
            return names
        except OSError as e:
            logger.error(f"Error listing audio programs in {self.audio_programs_dir}: {e}", exc_info=True)
            return []

    def delete_program(self, program_name):
        if not is_safe_filename_component(f"{program_name}.json"):
            logger.error(f"Attempted to delete audio program with unsafe name: {program_name}")
            return False

        file_path = self._get_program_file_path(program_name)
        logger.warning(f"Attempting to delete audio program: {file_path}")
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Audio program '{program_name}' deleted.")
            else:
                logger.info(f"Audio program '{program_name}' did not exist, nothing to delete.")
            return True
        except OSError as e:
            logger.error(f"Error deleting audio program {file_path}: {e}", exc_info=True)
            return False