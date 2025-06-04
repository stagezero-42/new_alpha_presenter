# myapp/gui/audio_import_dialog.py
import os
import logging

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QFileDialog,
    QCheckBox  # Added QCheckBox for completeness if used for overwrite
)
from PySide6.QtCore import Qt, Signal

from ..audio.audio_track_manager import AudioTrackManager  # For type hinting
from ..utils.paths import get_media_path, get_icon_file_path
from ..utils.security import is_safe_filename_component
from .widget_helpers import create_button
from .file_dialog_helpers import get_themed_open_filename  # Use consistent file dialog

logger = logging.getLogger(__name__)


class AudioImportDialog(QDialog):
    track_imported_signal = Signal(str)  # Emits the name of the newly imported track

    def __init__(self, parent=None, track_manager: AudioTrackManager = None):  # Added track_manager argument
        super().__init__(parent)
        self.setWindowTitle("Import Audio Track")

        # Store the passed track_manager or create a new one if not provided (though tests should provide a mock)
        if track_manager:
            self.track_manager = track_manager
        else:
            logger.warning("AudioImportDialog created without a track_manager, creating a new one.")
            self.track_manager = AudioTrackManager()

        self.selected_file_path = ""
        # self.detected_duration_ms = None # Duration detection is handled by AudioTrackManager

        self._setup_ui()
        self._update_ui_state()

        try:
            icon_path = get_icon_file_path("audio_icon.png") or get_icon_file_path("import.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set AudioImportDialog window icon: {e}")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # File selection
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Audio File:"))
        self.file_path_label = QLabel("No file selected.")
        self.file_path_label.setMinimumWidth(300)  # Allow space for long paths
        file_layout.addWidget(self.file_path_label)
        self.browse_button = create_button("Browse...", on_click=self.browse_file)
        file_layout.addWidget(self.browse_button)
        main_layout.addLayout(file_layout)

        # Track name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Track Name:"))
        self.track_name_edit = QLineEdit()
        self.track_name_edit.setPlaceholderText("Enter a unique name for this audio track")
        self.track_name_edit.textChanged.connect(self._update_ui_state)
        name_layout.addWidget(self.track_name_edit)
        main_layout.addLayout(name_layout)

        # Duration display (optional, if we want to show it after detection)
        # self.duration_label = QLabel("Duration: N/A")
        # main_layout.addWidget(self.duration_label)

        # Overwrite checkbox (if needed, for now, name validation handles existing)
        # self.overwrite_checkbox = QCheckBox("Overwrite if track name exists")
        # main_layout.addWidget(self.overwrite_checkbox)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        self.import_button = create_button("Import", "import.png", on_click=self.handle_import)
        self.cancel_button = create_button("Cancel", "cancel.png", on_click=self.reject)
        buttons_layout.addWidget(self.import_button)
        buttons_layout.addWidget(self.cancel_button)
        main_layout.addLayout(buttons_layout)

        self.setMinimumWidth(500)

    def browse_file(self):
        # Use the consistent themed file dialog helper
        file_path = get_themed_open_filename(
            self,
            "Select Audio File",
            get_media_path(),  # Start in media or a sensible default
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a)"  # Common audio formats
        )
        if file_path:
            self.selected_file_path = file_path
            self.file_path_label.setText(file_path)
            # Auto-fill track name from filename (without extension)
            base_name = os.path.basename(file_path)
            track_name_suggestion, _ = os.path.splitext(base_name)
            self.track_name_edit.setText(track_name_suggestion.replace(" ", "_"))  # Replace spaces
            logger.debug(f"File selected: {file_path}, suggested track name: {self.track_name_edit.text()}")
            # Duration detection can be triggered here if desired, or on import
            # self.detect_and_display_duration()
        else:
            self.selected_file_path = ""
            self.file_path_label.setText("No file selected.")
            self.track_name_edit.clear()
            # self.duration_label.setText("Duration: N/A")
        self._update_ui_state()

    # def detect_and_display_duration(self):
    #     """Placeholder if we want to detect and show duration before import."""
    #     if self.selected_file_path:
    #         # This part needs the actual duration detection logic, currently missing in AudioTrackManager
    #         # For now, this would rely on a method in self.track_manager
    #         # duration_ms = self.track_manager.detect_audio_duration(self.selected_file_path) # Assuming such method
    #         # if duration_ms is not None:
    #         #     self.duration_label.setText(f"Duration: {duration_ms / 1000.0:.2f} s")
    #         #     self.detected_duration_ms = duration_ms
    #         # else:
    #         #     self.duration_label.setText("Duration: Unknown")
    #         #     self.detected_duration_ms = None
    #         pass # No immediate duration display for now
    #     else:
    #         # self.duration_label.setText("Duration: N/A")
    #         # self.detected_duration_ms = None
    #         pass

    def validate_track_name(self) -> bool:
        track_name = self.track_name_edit.text().strip()
        if not track_name:
            QMessageBox.warning(self, "Invalid Name", "Track name cannot be empty.")
            return False

        safe_track_name = track_name.replace(" ", "_")
        if not is_safe_filename_component(f"{safe_track_name}.json"):  # Check safety for JSON filename
            QMessageBox.warning(self, "Invalid Name",
                                f"Track name '{track_name}' contains invalid characters or is a reserved name.")
            return False

        # Check if track name (after making it safe) already exists
        # Use the passed track_manager instance
        if safe_track_name in self.track_manager.list_audio_tracks():
            # if not self.overwrite_checkbox.isChecked(): # If overwrite option existed
            QMessageBox.warning(self, "Name Exists", f"A track with the name '{safe_track_name}' already exists.")
            return False
        return True

    def handle_import(self):
        if not self.selected_file_path:
            QMessageBox.warning(self, "Missing Information", "Please select an audio file to import.")
            return

        if not self.validate_track_name():
            return

        track_name = self.track_name_edit.text().strip().replace(" ", "_")

        # Use the passed track_manager instance
        metadata, error_msg = self.track_manager.create_metadata_from_file(
            track_name,
            self.selected_file_path
        )

        if metadata and error_msg is None:
            QMessageBox.information(self, "Success",
                                    f"Track '{metadata.get('track_name', track_name)}' imported successfully.")
            self.track_imported_signal.emit(metadata.get('track_name', track_name))
            self.accept()
        else:
            error_details = error_msg or "An unknown error occurred during import."
            QMessageBox.critical(self, "Import Failed", f"Could not import track: {error_details}")

    def _update_ui_state(self):
        can_import = bool(self.selected_file_path and self.track_name_edit.text().strip())
        self.import_button.setEnabled(can_import)

    def get_imported_track_info(self) -> dict | None:
        # This method might not be needed if using signals
        # But if dialog is used modally and info retrieved after, it could be.
        if self.result() == QDialog.DialogCode.Accepted:
            return {
                "track_name": self.track_name_edit.text().strip().replace(" ", "_"),
                "file_path": self.selected_file_path,  # This is the original source path
                # "detected_duration_ms": self.detected_duration_ms
            }
        return None