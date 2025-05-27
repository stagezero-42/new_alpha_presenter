# myapp/gui/file_dialog_helpers.py
import os
import logging
from PySide6.QtWidgets import QFileDialog, QDialog
from PySide6.QtGui import QIcon
from ..utils.paths import get_icon_file_path

logger = logging.getLogger(__name__)

def _configure_dialog(dialog):
    """Applies common configuration to a QFileDialog instance."""
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    try:
        icon_path = get_icon_file_path("app_icon.png")
        if icon_path and os.path.exists(icon_path):
            dialog.setWindowIcon(QIcon(icon_path))
    except Exception as e:
        logger.warning(f"Could not set icon for QFileDialog: {e}")

def get_themed_open_filename(parent, caption, directory, filter_str):
    """
    Shows a themed 'Open File' dialog and returns the selected filename.

    Returns:
        str or None: The full path to the selected file, or None if cancelled.
    """
    dialog = QFileDialog(parent, caption, directory, filter_str)
    _configure_dialog(dialog)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        selected_files = dialog.selectedFiles()
        return selected_files[0] if selected_files else None
    return None

def get_themed_open_filenames(parent, caption, directory, filter_str):
    """
    Shows a themed 'Open Files' dialog and returns selected filenames.

    Returns:
        list[str]: A list of full paths to selected files, or an empty list.
    """
    dialog = QFileDialog(parent, caption, directory, filter_str)
    _configure_dialog(dialog)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selectedFiles()
    return []

def get_themed_save_filename(parent, caption, directory, filter_str):
    """
    Shows a themed 'Save File' dialog and returns the selected filename.

    Returns:
        str or None: The full path to the selected file, or None if cancelled.
    """
    dialog = QFileDialog(parent, caption, directory, filter_str)
    _configure_dialog(dialog)
    dialog.setFileMode(QFileDialog.FileMode.AnyFile)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setDefaultSuffix("json") # Helps ensure .json is used

    if dialog.exec() == QDialog.DialogCode.Accepted:
        selected_files = dialog.selectedFiles()
        return selected_files[0] if selected_files else None
    return None