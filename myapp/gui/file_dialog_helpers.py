# myapp/gui/file_dialog_helpers.py
import os
import logging
from PySide6.QtWidgets import QFileDialog, QDialog
from PySide6.QtGui import QIcon
from ..utils.paths import get_icon_file_path

logger = logging.getLogger(__name__)

# --- MODIFIED: Added icon_name parameter ---
def _configure_dialog(dialog, icon_name):
    """Applies common configuration to a QFileDialog instance."""
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    try:
        icon_path = get_icon_file_path(icon_name) # Use the passed icon_name
        if icon_path and os.path.exists(icon_path):
            dialog.setWindowIcon(QIcon(icon_path))
        else:
            logger.warning(f"Could not find icon '{icon_name}' for QFileDialog.")
            # Optionally fall back to app_icon.png or no icon
            fallback_path = get_icon_file_path("app_icon.png")
            if fallback_path and os.path.exists(fallback_path):
                 dialog.setWindowIcon(QIcon(fallback_path))

    except Exception as e:
        logger.warning(f"Could not set icon '{icon_name}' for QFileDialog: {e}")
# --- END MODIFIED ---

# --- MODIFIED: Added icon_name parameter, default to 'load.png' ---
def get_themed_open_filename(parent, caption, directory, filter_str, icon_name="load.png"):
    """
    Shows a themed 'Open File' dialog and returns the selected filename.
    """
    dialog = QFileDialog(parent, caption, directory, filter_str)
    _configure_dialog(dialog, icon_name) # Pass the icon name
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        selected_files = dialog.selectedFiles()
        return selected_files[0] if selected_files else None
    return None
# --- END MODIFIED ---

# --- MODIFIED: Added icon_name parameter, default to 'load.png' ---
def get_themed_open_filenames(parent, caption, directory, filter_str, icon_name="load.png"):
    """
    Shows a themed 'Open Files' dialog and returns selected filenames.
    """
    dialog = QFileDialog(parent, caption, directory, filter_str)
    _configure_dialog(dialog, icon_name) # Pass the icon name
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selectedFiles()
    return []
# --- END MODIFIED ---

# --- MODIFIED: Added icon_name parameter, default to 'save.png' ---
def get_themed_save_filename(parent, caption, directory, filter_str, icon_name="save.png"):
    """
    Shows a themed 'Save File' dialog and returns the selected filename.
    """
    dialog = QFileDialog(parent, caption, directory, filter_str)
    _configure_dialog(dialog, icon_name) # Pass the icon name
    dialog.setFileMode(QFileDialog.FileMode.AnyFile)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setDefaultSuffix("json")

    if dialog.exec() == QDialog.DialogCode.Accepted:
        selected_files = dialog.selectedFiles()
        return selected_files[0] if selected_files else None
    return None
# --- END MODIFIED ---