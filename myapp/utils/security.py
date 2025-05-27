# myapp/utils/security.py
import os
import re

# Define a set of potentially problematic characters/names.
# We disallow path separators and control characters.
# We also disallow names that are just '.' or '..'.
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
        print("Security Warning: Filename is empty or not a string.")
        return False

    if _INVALID_CHARS_RE.search(filename):
        print(f"Security Warning: Filename '{filename}' contains invalid characters (/, \\, or null).")
        return False

    if filename in _INVALID_NAMES:
        print(f"Security Warning: Filename '{filename}' is '.' or '..'.")
        return False

    # Optional: Check for OS-specific reserved names (more complex)
    # e.g., on Windows: CON, PRN, AUX, NUL, COM1-9, LPT1-9

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
        # The warning is printed within is_safe_filename_component
        return None