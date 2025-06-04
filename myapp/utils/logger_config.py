# myapp/utils/logger_config.py
import logging
import logging.config
import os
# Corrected import: get_app_root_path instead of get_project_root
from .paths import get_app_root_path, get_log_file_path
from ..settings.settings_manager import SettingsManager  # For log level from settings

DEFAULT_LOG_LEVEL = "DEBUG"  # Fallback if settings can't be read early


def setup_logging():
    """
    Sets up the application-wide logging configuration.
    Reads log level and file logging settings from SettingsManager.
    """
    settings_manager = SettingsManager()
    log_level_str = settings_manager.get_setting("log_level", DEFAULT_LOG_LEVEL)
    log_to_file = settings_manager.get_setting("log_to_file", False)
    default_log_file = get_log_file_path()  # Default path from paths.py
    log_file_path = settings_manager.get_setting("log_file_path", default_log_file)

    # Ensure the directory for the log file exists
    if log_to_file:
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):  # Check if log_dir is not empty (e.g. root dir)
            try:
                os.makedirs(log_dir, exist_ok=True)
            except OSError as e:
                # Use basicConfig for console logging if directory creation fails
                logging.basicConfig(level=logging.ERROR,
                                    format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
                logging.error(f"Could not create log directory {log_dir}: {e}. File logging disabled.")
                log_to_file = False  # Disable file logging

    numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)

    handlers = {
        'console': {
            'class': 'logging.StreamHandler',
            'level': numeric_level,
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        }
    }
    if log_to_file:
        handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': numeric_level,
            'formatter': 'standard',
            'filename': log_file_path,
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 2,
            'encoding': 'utf-8'
        }

    handler_names = ['console']
    if log_to_file:
        handler_names.append('file')

    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
        },
        'handlers': handlers,
        'root': {  # Root logger configuration
            'handlers': handler_names,
            'level': numeric_level,
        },
        # Example of configuring a specific logger if needed
        # 'loggers': {
        #     'myapp': { # Configures loggers for the 'myapp' package
        #         'handlers': handler_names,
        #         'level': numeric_level, # Or a different level for just this package
        #         'propagate': False # Prevent messages from being passed to the root logger
        #     }
        # }
    }

    try:
        logging.config.dictConfig(logging_config)
        root_logger = logging.getLogger()  # Get the root logger
        # Update its level explicitly after dictConfig, as sometimes it might not stick
        root_logger.setLevel(numeric_level)
        for handler in root_logger.handlers:
            handler.setLevel(numeric_level)

        logging.info(f"Logging initialized. Level: {log_level_str}, File Logging: {log_to_file}" + (
            f", Log File: {log_file_path}" if log_to_file else ""))
    except Exception as e:
        # Fallback to basic config if dictConfig fails
        logging.basicConfig(level=numeric_level)
        logging.exception(f"Error configuring logging with dictConfig: {e}. Fell back to basicConfig.")


if __name__ == '__main__':
    # For testing the logger setup
    setup_logging()
    logger = logging.getLogger(__name__)  # Get logger for this module
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")

    # Test logging from another module (simulated)
    # In a real app, other_module_logger = logging.getLogger('myapp.other_module')
    other_module_logger = logging.getLogger('myapp.test_module')
    other_module_logger.info("Info message from another module.")