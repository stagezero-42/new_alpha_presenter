# myapp/gui/layer_editor_dialog.py
import os
import shutil
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QMessageBox, QAbstractItemView, QListWidgetItem,
    QLabel, QSpinBox, QFrame, QComboBox, QCheckBox, QFormLayout, QGroupBox
)
from PySide6.QtGui import QIcon
from .file_dialog_helpers import get_themed_open_filenames
from ..utils.paths import get_media_path, get_media_file_path, get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component
from ..text.paragraph_manager import ParagraphManager

logger = logging.getLogger(__name__)


class LayerEditorDialog(QDialog):
    def __init__(self, slide_layers, current_duration, current_loop_target,
                 current_text_overlay,  # Now includes new flags if present
                 display_window_instance, parent=None):
        super().__init__(parent)
        logger.debug(f"Initializing LayerEditorDialog. TextOverlay: {current_text_overlay}")
        self.setWindowTitle("Edit Slide Details")
        self.slide_layers = list(slide_layers)
        self.current_duration = current_duration
        self.current_loop_target = current_loop_target
        self.current_text_overlay = current_text_overlay if current_text_overlay else {}
        self.media_path = get_media_path()
        self.display_window = display_window_instance
        self.setMinimumSize(500, 750)  # Increased size for new options

        self.paragraph_manager = ParagraphManager()
        self.available_paragraphs = []

        try:
            icon_path = get_icon_file_path("edit.png")
            if icon_path and os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set LayerEditorDialog window icon: {e}", exc_info=True)

        self.setup_ui()
        self.populate_layers_list()
        self.duration_spinbox.setValue(self.current_duration)
        self.loop_target_spinbox.setValue(self.current_loop_target)
        self.load_text_overlay_ui()
        self.update_text_fields_state()
        logger.debug("LayerEditorDialog initialized.")

    def setup_ui(self):
        logger.debug("Setting up LayerEditorDialog UI...")
        main_layout = QVBoxLayout(self)

        # Layers Section
        layers_group = QGroupBox("Image Layers")
        layers_layout = QVBoxLayout(layers_group)
        layers_layout.addWidget(QLabel("Image Layers (drag to reorder):"))
        self.layers_list_widget = QListWidget()
        self.layers_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        layers_layout.addWidget(self.layers_list_widget)
        layers_buttons_layout = QHBoxLayout()
        self.add_layer_button = create_button(" Add Image(s)", "add.png", on_click=self.add_layers)
        self.remove_layer_button = create_button(" Remove Selected", "remove.png", on_click=self.remove_layer)
        layers_buttons_layout.addWidget(self.add_layer_button)
        layers_buttons_layout.addWidget(self.remove_layer_button)
        layers_layout.addLayout(layers_buttons_layout)
        main_layout.addWidget(layers_group)

        # Timing/Looping Section
        timing_loop_group = QGroupBox("Timing & Looping")
        timing_loop_layout = QFormLayout(timing_loop_group)
        self.duration_label = QLabel("Auto-advance after (seconds, 0 for manual):")
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setMinimum(0)
        self.duration_spinbox.setMaximum(3600)
        self.duration_spinbox.setSuffix(" s")
        timing_loop_layout.addRow(self.duration_label, self.duration_spinbox)
        loop_label = QLabel("After duration, loop to slide # (1-based, 0 for none):")
        self.loop_target_spinbox = QSpinBox()
        self.loop_target_spinbox.setMinimum(0)
        self.loop_target_spinbox.setMaximum(999)
        timing_loop_layout.addRow(loop_label, self.loop_target_spinbox)
        main_layout.addWidget(timing_loop_group)

        # Text Overlay Section
        text_overlay_group = QGroupBox("Text Overlay")
        text_overlay_layout = QFormLayout(text_overlay_group)
        self.paragraph_combo = QComboBox()
        self.paragraph_combo.addItem("(None)", None)
        self.available_paragraphs = sorted(self.paragraph_manager.list_paragraphs())
        for para_name in self.available_paragraphs:
            self.paragraph_combo.addItem(para_name, para_name)
        self.paragraph_combo.currentIndexChanged.connect(self.update_text_fields_state)
        text_overlay_layout.addRow("Paragraph:", self.paragraph_combo)
        self.start_sentence_spinbox = QSpinBox()
        self.start_sentence_spinbox.setMinimum(1)
        self.start_sentence_spinbox.setMaximum(999)
        self.start_sentence_spinbox.valueChanged.connect(self.validate_sentence_range)
        text_overlay_layout.addRow("Start Sentence (1-based):", self.start_sentence_spinbox)
        self.end_sentence_spinbox = QSpinBox()
        self.end_sentence_spinbox.setMinimum(1)
        self.end_sentence_spinbox.setMaximum(999)
        self.end_all_checkbox = QCheckBox("Use 'All' Sentences")
        self.end_all_checkbox.toggled.connect(self.update_text_fields_state)
        end_layout = QHBoxLayout()
        end_layout.addWidget(self.end_sentence_spinbox)
        end_layout.addWidget(self.end_all_checkbox)
        text_overlay_layout.addRow("End Sentence (1-based):", end_layout)

        # --- NEW CHECKBOXES ---
        self.sentence_timing_check = QCheckBox("Enable Sentence Timers")
        self.sentence_timing_check.setToolTip("Auto-advance sentences based on their individual delays.")
        text_overlay_layout.addRow("", self.sentence_timing_check)

        self.auto_advance_slide_check = QCheckBox("Auto-Advance to Next Slide")
        self.auto_advance_slide_check.setToolTip("When the last sentence's timer ends, move to the next slide.")
        text_overlay_layout.addRow("", self.auto_advance_slide_check)
        # --- END NEW CHECKBOXES ---

        main_layout.addWidget(text_overlay_group)

        # Dialog Buttons
        ok_cancel_layout = QHBoxLayout()
        self.preview_button = create_button(" Preview Slide", "preview.png",
                                            on_click=self.preview_slide_on_display_from_editor)
        self.ok_button = create_button("OK", on_click=self.accept_changes)
        self.cancel_button = create_button("Cancel", on_click=self.reject)
        ok_cancel_layout.addWidget(self.preview_button)
        ok_cancel_layout.addStretch()
        ok_cancel_layout.addWidget(self.ok_button)
        ok_cancel_layout.addWidget(self.cancel_button)
        main_layout.addLayout(ok_cancel_layout)
        logger.debug("LayerEditorDialog UI setup complete.")

    def load_text_overlay_ui(self):
        """Populates text overlay UI fields from self.current_text_overlay."""
        para_name = self.current_text_overlay.get("paragraph_name")
        start_sent = self.current_text_overlay.get("start_sentence", 1)
        end_sent = self.current_text_overlay.get("end_sentence", 1)
        # --- NEW: Load flags ---
        sent_timing = self.current_text_overlay.get("sentence_timing_enabled", False)
        slide_advance = self.current_text_overlay.get("auto_advance_slide", False)
        # --- END NEW ---

        if para_name and para_name in self.available_paragraphs:
            self.paragraph_combo.setCurrentText(para_name)
        else:
            self.paragraph_combo.setCurrentIndex(0)

        self.start_sentence_spinbox.setValue(start_sent)
        if isinstance(end_sent, str) and end_sent.lower() == "all":
            self.end_all_checkbox.setChecked(True)
        else:
            self.end_all_checkbox.setChecked(False)
            self.end_sentence_spinbox.setValue(end_sent)

        # --- NEW: Set flags ---
        self.sentence_timing_check.setChecked(sent_timing)
        self.auto_advance_slide_check.setChecked(slide_advance)
        # --- END NEW ---
        self.validate_sentence_range()

    def update_text_fields_state(self):
        """Enables/disables text fields based on selections."""
        paragraph_selected = self.paragraph_combo.currentData() is not None
        use_all_sentences = self.end_all_checkbox.isChecked()

        self.start_sentence_spinbox.setEnabled(paragraph_selected)
        self.end_sentence_spinbox.setEnabled(paragraph_selected and not use_all_sentences)
        self.end_all_checkbox.setEnabled(paragraph_selected)
        # --- NEW: Update flags state ---
        self.sentence_timing_check.setEnabled(paragraph_selected)
        self.auto_advance_slide_check.setEnabled(paragraph_selected and self.sentence_timing_check.isChecked())
        # --- END NEW ---

        if paragraph_selected:
            self.duration_label.setText("Initial Text Delay (seconds, 0 for none):")
            loaded_para = self.paragraph_manager.load_paragraph(self.paragraph_combo.currentData())
            if loaded_para:
                num_sentences = len(loaded_para.get("sentences", []))
                self.start_sentence_spinbox.setMaximum(max(1, num_sentences))
                if not use_all_sentences:
                    self.end_sentence_spinbox.setMaximum(max(1, num_sentences))
                self.validate_sentence_range()
        else:
            self.duration_label.setText("Auto-advance after (seconds, 0 for manual):")
            self.start_sentence_spinbox.setValue(1);
            self.end_sentence_spinbox.setValue(1)
            self.start_sentence_spinbox.setMaximum(999);
            self.end_sentence_spinbox.setMaximum(999)

    def validate_sentence_range(self):
        """Ensures end_sentence is not less than start_sentence."""
        if not self.end_all_checkbox.isChecked():
            start_val = self.start_sentence_spinbox.value()
            self.end_sentence_spinbox.setMinimum(start_val)
            if self.end_sentence_spinbox.value() < start_val:
                self.end_sentence_spinbox.setValue(start_val)

    def populate_layers_list(self):
        self.layers_list_widget.clear()
        for layer_path in self.slide_layers:
            self.layers_list_widget.addItem(QListWidgetItem(layer_path))

    def add_layers(self):
        file_names = get_themed_open_filenames(self, "Select Images", self.media_path,
                                               "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg)")
        if not file_names: return

        added_count = 0
        for source_path in file_names:
            filename = os.path.basename(source_path)
            if not is_safe_filename_component(filename):
                QMessageBox.warning(self, "Unsafe Filename", f"Skipped: {filename}")
                continue

            dest_path = get_media_file_path(filename)
            final_filename = filename

            if os.path.exists(dest_path) and not os.path.samefile(source_path, dest_path):
                base, ext = os.path.splitext(filename)
                i = 1
                while True:
                    final_filename = f"{base}_{i:03d}{ext}"
                    new_dest = get_media_file_path(final_filename)
                    if not os.path.exists(new_dest): dest_path = new_dest; break
                    i += 1

            try:
                if not os.path.exists(dest_path): shutil.copy2(source_path, dest_path)
                if final_filename not in self.slide_layers:
                    self.slide_layers.append(final_filename);
                    added_count += 1
            except OSError as e:
                QMessageBox.critical(self, "Copy Error", f"Could not copy {filename}: {e}")

        if added_count > 0: self.populate_layers_list()

    def remove_layer(self):
        current_item = self.layers_list_widget.currentItem()
        if not current_item: return
        row = self.layers_list_widget.row(current_item)
        self.slide_layers.pop(row)
        self.populate_layers_list()

    def preview_slide_on_display_from_editor(self):
        if not self.display_window: return
        self.update_internal_layers_from_widget()
        self.display_window.display_images(self.slide_layers)

    def update_internal_layers_from_widget(self):
        self.slide_layers = [self.layers_list_widget.item(i).text() for i in range(self.layers_list_widget.count())]

    def accept_changes(self):
        self.update_internal_layers_from_widget()
        self.accept()

    def get_updated_slide_data(self):
        data = {
            "layers": self.slide_layers,
            "duration": self.duration_spinbox.value(),
            "loop_to_slide": self.loop_target_spinbox.value(),
            "text_overlay": None
        }
        selected_para_name = self.paragraph_combo.currentData()
        if selected_para_name:
            data["text_overlay"] = {
                "paragraph_name": selected_para_name,
                "start_sentence": self.start_sentence_spinbox.value(),
                "end_sentence": "all" if self.end_all_checkbox.isChecked() else self.end_sentence_spinbox.value(),
                # --- NEW: Save flags ---
                "sentence_timing_enabled": self.sentence_timing_check.isChecked(),
                "auto_advance_slide": self.auto_advance_slide_check.isChecked()
                # --- END NEW ---
            }
        logger.debug(f"Returning updated slide data: {data}")
        return data