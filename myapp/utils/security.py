# myapp/utils/security.py
import os
import re
import logging  # Import logging

logger = logging.getLogger(__name__)  # Get logger for this module

_INVALID_CHARS_RE = re.compile(r'[\0/\\]')
_INVALID_NAMES = {'.', '..'}

def is_safe_filename_component(filename):
    """
    Checks if a filename component is safe for use in a path.

    It checks for:
    1. Null bytes.
    2. Path separators ('/' or '\').
    3. If the name is exactly '.' or '..'.

    Args:
        filename (str): The filename component to check.

    Returns:
        bool: True if the filename is considered safe, False otherwise.
    """
    if not filename or not isinstance(filename, str):
        logger.warning("Security Warning: Filename is empty or not a string.")
        return False

    if _INVALID_CHARS_RE.search(filename):
        logger.warning(f"Security Warning: Filename '{filename}' contains invalid characters (/, \\, or null).")
        return False

    if filename in _INVALID_NAMES:
        logger.warning(f"Security Warning: Filename '{filename}' is '.' or '..'.")
        return False

    return True

def get_safe_basename(path_from_dialog):
    """
    Gets the basename and validates it using is_safe_filename_component.

    Args:
        path_from_dialog (str): The full path typically received from a dialog.

    Returns:
        str or None: The safe basename if valid, otherwise None.
    """
    basename = os.path.basename(path_from_dialog)
    if is_safe_filename_component(basename):
        return basename
    else:
        return None