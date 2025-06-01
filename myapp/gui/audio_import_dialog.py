# myapp/gui/audio_import_dialog.py
import os
import logging
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QMessageBox, QFileDialog, QLabel
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_icon_file_path, get_media_path, get_media_file_path
from ..utils.security import is_safe_filename_component
from .widget_helpers import create_button

logger = logging.getLogger(__name__)


class AudioImportDialog(QDialog):
    audio_track_imported = Signal(str)

    def __init__(self, parent=None, audio_track_manager: AudioTrackManager = None):
        super().__init__(parent)
        self.setWindowTitle("Import Audio File")
        self.setMinimumSize(500, 200)

        self.audio_track_manager = audio_track_manager if audio_track_manager else AudioTrackManager()

        self.source_audio_file_path = ""
        self.target_media_filename = ""

        self._setup_ui()
        self._set_window_icon()

    def _set_window_icon(self):
        try:
            icon_path = get_icon_file_path("audio_icon.png") or get_icon_file_path("import.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set AudioImportDialog icon: {e}", exc_info=True)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        file_selection_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select an audio file (e.g., .mp3, .wav)...")
        self.file_path_edit.setReadOnly(True)
        file_selection_layout.addWidget(self.file_path_edit)
        browse_button = create_button("Browse...", on_click=self._browse_file)
        file_selection_layout.addWidget(browse_button)
        form_layout.addRow("Audio File:", file_selection_layout)

        self.track_name_edit = QLineEdit()
        self.track_name_edit.setPlaceholderText("Enter unique name for this audio track (e.g., my_song)")
        form_layout.addRow("Track Name (for metadata):", self.track_name_edit)  # Clarified label

        main_layout.addLayout(form_layout)
        main_layout.addWidget(
            QLabel("The audio file will be copied to the project's media directory if it's not already there."))

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        import_button = create_button("Import", "import.png", on_click=self._handle_import)
        cancel_button = create_button("Cancel", on_click=self.reject)
        button_layout.addWidget(import_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _browse_file(self):
        start_dir = get_media_path()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", start_dir,
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.aac *.m4a);;All Files (*)"  # Added more common types
        )
        if file_path:
            self.source_audio_file_path = file_path
            self.file_path_edit.setText(file_path)

            base_name = os.path.basename(file_path)
            self.target_media_filename = base_name

            suggested_track_name = os.path.splitext(base_name)[0].replace(" ", "_").lower()
            self.track_name_edit.setText(suggested_track_name)

    def _validate_track_name(self, name: str) -> tuple[bool, str]:
        safe_name = name.strip().replace(" ", "_")
        if not safe_name:
            return False, "Track name cannot be empty."
        if not is_safe_filename_component(f"{safe_name}.json"):
            return False, "Track name contains invalid characters or is reserved."

        existing_tracks = self.audio_track_manager.list_audio_tracks()
        if safe_name in existing_tracks:
            return False, f"An audio track named '{safe_name}' already exists. Choose a different name."
        return True, safe_name

    def _handle_import(self):
        if not self.source_audio_file_path:
            QMessageBox.warning(self, "No File", "Please select an audio file to import.")
            return

        track_name_input = self.track_name_edit.text()
        is_valid_name, msg_or_safe_name = self._validate_track_name(track_name_input)
        if not is_valid_name:
            QMessageBox.warning(self, "Invalid Track Name", msg_or_safe_name)
            return
        safe_track_name = msg_or_safe_name

        target_media_dir = get_media_path()
        final_media_path_in_assets = get_media_file_path(self.target_media_filename)

        try:
            if not os.path.exists(target_media_dir):
                os.makedirs(target_media_dir, exist_ok=True)

            if os.path.abspath(self.source_audio_file_path) != os.path.abspath(final_media_path_in_assets):
                logger.info(
                    f"Copying audio file from '{self.source_audio_file_path}' to '{final_media_path_in_assets}'")
                shutil.copy2(self.source_audio_file_path, final_media_path_in_assets)
            else:
                logger.info(f"Audio file '{self.target_media_filename}' is already in the media directory.")
        except Exception as e:
            logger.error(f"Error copying audio file '{self.target_media_filename}': {e}", exc_info=True)
            QMessageBox.critical(self, "File Copy Error", f"Could not copy audio file to media directory: {e}")
            return

        # Detect duration using the copied file in assets
        logger.info(f"Attempting to detect duration for: {final_media_path_in_assets}")
        detected_duration_ms = self.audio_track_manager.detect_audio_duration(final_media_path_in_assets)
        if detected_duration_ms is None:
            QMessageBox.warning(self, "Duration Not Detected",
                                f"Could not automatically detect the duration for '{self.target_media_filename}'. "
                                "It will be stored as unknown (null). You may need to verify it manually.")
        else:
            logger.info(f"Detected duration {detected_duration_ms}ms for '{self.target_media_filename}'")

        track_metadata = {
            "track_name": safe_track_name,
            "file_path": self.target_media_filename,
            "detected_duration_ms": detected_duration_ms
        }

        if self.audio_track_manager.save_track_metadata(safe_track_name, track_metadata):
            QMessageBox.information(self, "Import Successful", f"Audio track '{safe_track_name}' metadata created.")
            self.audio_track_imported.emit(safe_track_name)
            self.accept()
        else:
            QMessageBox.critical(self, "Save Error", f"Failed to save audio track metadata for '{safe_track_name}'.")