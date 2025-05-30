# myapp/gui/text_import_dialog.py
import os
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QComboBox, QMessageBox,
    QFileDialog, QLabel, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from ..text.text_parser import parse_srt, parse_webvtt, parse_tsv, parse_plain_text
from ..text.paragraph_manager import ParagraphManager
from ..utils.paths import get_icon_file_path, get_texts_path
from ..utils.security import is_safe_filename_component
from .widget_helpers import create_button  # Assuming this is still preferred

logger = logging.getLogger(__name__)


class TextImportDialog(QDialog):
    paragraph_imported = Signal(str)  # Emits the name of the successfully imported paragraph

    IMPORT_FORMATS = {
        "SRT (SubRip Subtitle)": "srt",
        "WebVTT (Web Video Text Tracks)": "vtt",
        "TSV (Tab-Separated Values)": "tsv",
        "Plain Text Block": "txt"
    }

    def __init__(self, parent=None, paragraph_manager: ParagraphManager = None):
        super().__init__(parent)
        self.setWindowTitle("Import Text File")
        self.setMinimumSize(500, 400)

        if paragraph_manager is None:
            # Fallback, though it should always be provided
            self.paragraph_manager = ParagraphManager()
            logger.warning("TextImportDialog initialized without a ParagraphManager instance. Using a new one.")
        else:
            self.paragraph_manager = paragraph_manager

        self.file_content = ""
        self.imported_paragraph_name = None  # To store the name after successful import

        self._setup_ui()
        self._set_window_icon()

    def _set_window_icon(self):
        try:
            icon_path = get_icon_file_path("import.png") or get_icon_file_path("text.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set TextImportDialog icon: {e}", exc_info=True)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # File Selection
        file_selection_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select a text file to import...")
        self.file_path_edit.setReadOnly(True)
        file_selection_layout.addWidget(self.file_path_edit)
        browse_button = create_button("Browse...", on_click=self._browse_file)
        file_selection_layout.addWidget(browse_button)
        form_layout.addRow("File:", file_selection_layout)

        # Format Selection
        self.format_combo = QComboBox()
        self.format_combo.addItems(self.IMPORT_FORMATS.keys())
        self.format_combo.setCurrentText("Plain Text Block")
        form_layout.addRow("Import Format:", self.format_combo)
        self.format_combo.currentTextChanged.connect(self._update_preview_and_help)

        # Paragraph Name
        self.paragraph_name_edit = QLineEdit()
        self.paragraph_name_edit.setPlaceholderText("Enter name for new paragraph (e.g., my_imported_text)")
        form_layout.addRow("Paragraph Name:", self.paragraph_name_edit)

        main_layout.addLayout(form_layout)

        # Preview Area (Optional, simple for now)
        self.preview_label = QLabel("File Preview / Format Helper:")
        main_layout.addWidget(self.preview_label)
        self.preview_text_edit = QTextEdit()
        self.preview_text_edit.setReadOnly(True)
        self.preview_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)  # Good for structured text
        main_layout.addWidget(self.preview_text_edit, 1)  # Stretch factor
        self._update_preview_and_help(self.format_combo.currentText())  # Initial help text

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        import_button = create_button("Import", "import.png", on_click=self._handle_import)
        cancel_button = create_button("Cancel", on_click=self.reject)
        button_layout.addWidget(import_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _update_preview_and_help(self, format_name_key):
        format_short = self.IMPORT_FORMATS.get(format_name_key, "txt")
        help_text = ""
        if not self.file_content:
            if format_short == "srt":
                help_text = "SRT Format Example:\n1\n00:00:01,000 --> 00:00:05,000\nText line 1\nText line 2\n\n2\n..."
            elif format_short == "vtt":
                help_text = "WebVTT Format Example:\nWEBVTT\n\n00:01.000 --> 00:05.000\nText line 1\n\n00:06.000 --> 00:10.000\nText line 2"
            elif format_short == "tsv":
                help_text = "TSV Format Example (Tab-separated, times in milliseconds):\nstart\tend\ttext\n0\t5000\tFirst line of text\n5500\t10000\tSecond line"
            elif format_short == "txt":
                help_text = "Plain Text Format: Each non-empty line will be treated as a separate sentence with a default duration of 0s."
            self.preview_text_edit.setPlainText(help_text)
        else:
            # Display first N lines of actual file content if loaded
            max_preview_lines = 50
            preview_content = "\n".join(self.file_content.splitlines()[:max_preview_lines])
            if len(self.file_content.splitlines()) > max_preview_lines:
                preview_content += "\n\n[... file truncated for preview ...]"
            self.preview_text_edit.setPlainText(preview_content)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Text File", "",
            "Text Files (*.txt *.srt *.vtt *.tsv);;All Files (*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig to handle BOM
                    self.file_content = f.read()

                base_name = os.path.basename(file_path)
                suggested_para_name = os.path.splitext(base_name)[0].replace(" ", "_").lower()
                self.paragraph_name_edit.setText(suggested_para_name)
                self._update_preview_and_help(self.format_combo.currentText())

            except Exception as e:
                QMessageBox.critical(self, "File Read Error", f"Could not read file: {e}")
                self.file_content = ""
                self.file_path_edit.clear()
                self.paragraph_name_edit.clear()
                self._update_preview_and_help(self.format_combo.currentText())

    def _validate_paragraph_name(self, name: str) -> (bool, str):
        """Validates the paragraph name. Returns (isValid, message_or_safename)."""
        safe_name = name.strip().replace(" ", "_")
        if not safe_name:
            return False, "Paragraph name cannot be empty."
        if not is_safe_filename_component(f"{safe_name}.json"):
            return False, "Paragraph name contains invalid characters or is a reserved name (e.g., '.', '..')."

        # Check for existence using ParagraphManager's list_paragraphs
        # This requires ParagraphManager to be available
        existing_paragraphs = self.paragraph_manager.list_paragraphs()
        if safe_name in existing_paragraphs:
            return False, f"A paragraph named '{safe_name}' already exists. Please choose a different name."

        return True, safe_name

    def _handle_import(self):
        if not self.file_content:
            QMessageBox.warning(self, "No File", "Please select a file to import.")
            return

        para_name_input = self.paragraph_name_edit.text()
        is_valid_name, msg_or_safe_name = self._validate_paragraph_name(para_name_input)
        if not is_valid_name:
            QMessageBox.warning(self, "Invalid Name", msg_or_safe_name)
            return

        safe_paragraph_name = msg_or_safe_name
        selected_format_key = self.format_combo.currentText()
        format_short_code = self.IMPORT_FORMATS.get(selected_format_key, "txt")

        parsed_sentences = []
        try:
            if format_short_code == "srt":
                parsed_sentences = parse_srt(self.file_content)
            elif format_short_code == "vtt":
                parsed_sentences = parse_webvtt(self.file_content)
            elif format_short_code == "tsv":
                parsed_sentences = parse_tsv(self.file_content)
            elif format_short_code == "txt":
                parsed_sentences = parse_plain_text(self.file_content)

            if not parsed_sentences:
                QMessageBox.warning(self, "Parsing Issue",
                                    "No sentences were parsed from the file. The format might be incorrect or the file empty of parsable content.")
                return

        except Exception as e:
            logger.error(f"Error during parsing of {format_short_code}: {e}", exc_info=True)
            QMessageBox.critical(self, "Parsing Error", f"An error occurred while parsing the file: {e}")
            return

        paragraph_data = {
            "name": safe_paragraph_name,
            "sentences": parsed_sentences
        }

        try:
            if self.paragraph_manager.save_paragraph(safe_paragraph_name, paragraph_data):
                self.imported_paragraph_name = safe_paragraph_name  # Store for retrieval after dialog closes
                QMessageBox.information(self, "Import Successful",
                                        f"Paragraph '{safe_paragraph_name}' imported successfully with {len(parsed_sentences)} sentences.")
                self.paragraph_imported.emit(safe_paragraph_name)
                self.accept()  # Close dialog with Accepted status
            else:
                QMessageBox.critical(self, "Save Error",
                                     f"Failed to save the imported paragraph '{safe_paragraph_name}'.")
        except Exception as e:
            logger.error(f"Error saving imported paragraph '{safe_paragraph_name}': {e}", exc_info=True)
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred while saving: {e}")

    def get_imported_paragraph_name(self):
        """Returns the name of the paragraph that was successfully imported."""
        return self.imported_paragraph_name