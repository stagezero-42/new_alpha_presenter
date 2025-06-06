# myapp/gui/video_editor_dialog.py
import os
import logging
import shutil

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

from .widget_helpers import create_button
from .file_dialog_helpers import get_themed_open_filename
from ..utils.paths import get_media_path, get_media_file_path, get_icon_file_path
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)


class VideoEditorDialog(QDialog):
    """A dialog to select a video file and a thumbnail for a new video slide."""
    # This signal now emits the complete slide data dictionary
    video_slide_data_updated = Signal(dict)

    def __init__(self, parent=None, initial_video_path=None, initial_thumbnail_path=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Video Slide Details")
        self.setMinimumWidth(500)

        self.selected_video_path = initial_video_path
        self.selected_thumbnail_path = initial_thumbnail_path
        self.media_path = get_media_path()

        self._setup_ui()
        self._set_window_icon()

        # Populate fields if editing
        if self.selected_video_path:
            self.video_path_label.setText(os.path.basename(self.selected_video_path))
        if self.selected_thumbnail_path:
            self.thumb_path_label.setText(os.path.basename(self.selected_thumbnail_path))

        self._update_ok_button_state()

    def _set_window_icon(self):
        try:
            icon_path = get_icon_file_path("video.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set VideoEditorDialog icon: {e}")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        video_layout = QHBoxLayout()
        video_layout.addWidget(QLabel("Video File:"))
        self.video_path_label = QLabel("No file selected.")
        self.video_path_label.setMinimumWidth(300)
        video_layout.addWidget(self.video_path_label, 1)
        browse_video_button = create_button("Browse...", on_click=self._browse_video)
        video_layout.addWidget(browse_video_button)
        main_layout.addLayout(video_layout)

        thumb_layout = QHBoxLayout()
        thumb_layout.addWidget(QLabel("Thumbnail Image:"))
        self.thumb_path_label = QLabel("No file selected.")
        thumb_layout.addWidget(self.thumb_path_label, 1)
        browse_thumb_button = create_button("Browse...", on_click=self._browse_thumbnail)
        thumb_layout.addWidget(browse_thumb_button)
        main_layout.addLayout(thumb_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.ok_button = create_button("OK", on_click=self._handle_ok)
        cancel_button = create_button("Cancel", on_click=self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _browse_video(self):
        # When Browse, we expect the user is picking a file from their system, not from the media dir
        file_path = get_themed_open_filename(
            self, "Select Video File", "",  # Start in last used directory
            "Video Files (*.mp4 *.mov *.avi *.mkv)"
        )
        if file_path:
            self.selected_video_path = file_path
            self.video_path_label.setText(os.path.basename(file_path))
        self._update_ok_button_state()

    def _browse_thumbnail(self):
        file_path = get_themed_open_filename(
            self, "Select Thumbnail Image", "",  # Start in last used directory
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.selected_thumbnail_path = file_path
            self.thumb_path_label.setText(os.path.basename(file_path))
        self._update_ok_button_state()

    def _update_ok_button_state(self):
        self.ok_button.setEnabled(bool(self.selected_video_path and self.selected_thumbnail_path))

    def _copy_file_to_media(self, source_path):
        """Copies a file to the media directory if needed and returns the safe basename."""
        if not source_path or not os.path.exists(source_path):
            return None, f"Source file does not exist or is not specified: {source_path}"

        filename = os.path.basename(source_path)
        if not is_safe_filename_component(filename):
            return None, f"Filename contains invalid characters: {filename}"

        dest_path = get_media_file_path(filename)

        # Check if the file is already the one in the media directory
        if os.path.exists(dest_path) and os.path.samefile(source_path, dest_path):
            logger.debug(f"File '{filename}' is already in the media directory.")
            return filename, None  # File is already in place

        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied '{filename}' to media directory.")
        except Exception as e:
            return None, f"Failed to copy '{filename}': {e}"

        return filename, None

    def _handle_ok(self):
        # We need to handle the case where the user is editing and doesn't change a file.
        # The path will be a basename, not a full system path.

        video_source_is_full_path = os.path.isabs(self.selected_video_path)
        thumb_source_is_full_path = os.path.isabs(self.selected_thumbnail_path)

        video_filename = os.path.basename(self.selected_video_path)
        thumb_filename = os.path.basename(self.selected_thumbnail_path)

        if video_source_is_full_path:
            video_filename, error = self._copy_file_to_media(self.selected_video_path)
            if error:
                QMessageBox.critical(self, "Video File Error", error)
                return

        if thumb_source_is_full_path:
            thumb_filename, error = self._copy_file_to_media(self.selected_thumbnail_path)
            if error:
                QMessageBox.critical(self, "Thumbnail File Error", error)
                return

        slide_data = {
            "layers": [],
            "duration": 0,
            "loop_to_slide": 0,
            "text_overlay": None,
            "video_path": video_filename,
            "thumbnail_path": thumb_filename
        }
        self.video_slide_data_updated.emit(slide_data)
        self.accept()