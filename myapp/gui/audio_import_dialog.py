# myapp/gui/audio_import_dialog.py
import os
import logging

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QFileDialog,
    QCheckBox
)
from PySide6.QtCore import Qt, Signal

from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_media_path, get_icon_file_path
from ..utils.security import is_safe_filename_component
from .widget_helpers import create_button
from .file_dialog_helpers import get_themed_open_filename

logger = logging.getLogger(__name__)


class AudioImportDialog(QDialog):
    track_imported_signal = Signal(str)

    def __init__(self, parent=None, track_manager: AudioTrackManager = None):
        super().__init__(parent)
        self.setWindowTitle("Import Audio Track")

        if track_manager:
            self.track_manager = track_manager
        else:
            logger.warning("AudioImportDialog created without a track_manager, creating a new one.")
            self.track_manager = AudioTrackManager()

        self.selected_file_path = ""
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
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Audio File:"))
        self.file_path_label = QLabel("No file selected.")
        self.file_path_label.setMinimumWidth(300)
        file_layout.addWidget(self.file_path_label)
        self.browse_button = create_button("Browse...", on_click=self.browse_file)
        file_layout.addWidget(self.browse_button)
        main_layout.addLayout(file_layout)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Track Name:"))
        self.track_name_edit = QLineEdit()
        self.track_name_edit.setPlaceholderText("Enter a unique name for this audio track")
        self.track_name_edit.textChanged.connect(self._update_ui_state)
        name_layout.addWidget(self.track_name_edit)
        main_layout.addLayout(name_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        self.import_button = create_button("Import", "import.png", on_click=self.handle_import)
        self.cancel_button = create_button("Cancel", "cancel.png", on_click=self.reject)
        buttons_layout.addWidget(self.import_button)
        buttons_layout.addWidget(self.cancel_button)
        main_layout.addLayout(buttons_layout)
        self.setMinimumWidth(500)

    def browse_file(self):
        file_path = get_themed_open_filename(
            self, "Select Audio File", get_media_path(),
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a)"
        )
        if file_path:
            self.selected_file_path = file_path
            self.file_path_label.setText(file_path)
            base_name = os.path.basename(file_path)
            track_name_suggestion, _ = os.path.splitext(base_name)
            self.track_name_edit.setText(track_name_suggestion.replace(" ", "_"))
            logger.debug(f"File selected: {file_path}, suggested track name: {self.track_name_edit.text()}")
        else:
            self.selected_file_path = ""
            self.file_path_label.setText("No file selected.")
            self.track_name_edit.clear()
        self._update_ui_state()

    def validate_track_name(self) -> bool:
        track_name = self.track_name_edit.text().strip()
        if not track_name:
            QMessageBox.warning(self, "Invalid Name", "Track name cannot be empty.")
            return False

        safe_track_name = track_name.replace(" ", "_")
        if not is_safe_filename_component(f"{safe_track_name}.json"):
            QMessageBox.warning(self, "Invalid Name",
                                f"Track name '{track_name}' contains invalid characters or is a reserved name.")
            return False
        if safe_track_name in self.track_manager.list_audio_tracks():
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
        metadata, error_msg = self.track_manager.create_metadata_from_file(
            track_name, self.selected_file_path
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
        if self.result() == QDialog.DialogCode.Accepted:
            return {
                "track_name": self.track_name_edit.text().strip().replace(" ", "_"),
                "file_path": self.selected_file_path,
            }
        return None