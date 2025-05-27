# myapp/utils/logger_config.py
import logging
import sys
import os
from .paths import get_project_root

LOG_DIR_NAME = "logs"

def get_log_dir():
    """Returns the absolute path to the log directory."""
    return os.path.join(get_project_root(), LOG_DIR_NAME)

def setup_logging(log_level_str='INFO', log_to_file=False, log_filename='alphapresenter.log'):
    """
    Sets up the root logger for the application.

    Args:
        log_level_str (str): The desired logging level ('DEBUG', 'INFO', etc.).
        log_to_file (bool): Whether to log to a file.
        log_filename (str): The name of the file to log to (within the log dir).
    """
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    log_format = '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
    formatter = logging.Formatter(log_format)

    # Get the root logger
    root_logger = logging.getLogger()
    # Ensure we don't add handlers multiple times if this is called again
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(log_level)

    # Console Handler (always add)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level) # Console shows messages at the set level or higher
    root_logger.addHandler(console_handler)

    # File Handler (optional)
    if log_to_file:
        try:
            log_dir = get_log_dir()
            os.makedirs(log_dir, exist_ok=True)
            file_path = os.path.join(log_dir, log_filename)
            # Use RotatingFileHandler for larger applications, but FileHandler is simpler for now
            file_handler = logging.FileHandler(file_path, mode='a', encoding='utf-8')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG) # Log DEBUG and higher to file
            root_logger.addHandler(file_handler)
            logging.info(f"Logging to file enabled: {file_path}")
        except Exception as e:
            logging.error(f"Failed to set up file logging to {log_filename}: {e}", exc_info=True)

    logging.info(f"Logging initialized. Level: {log_level_str}, File Logging: {log_to_file}")