# myapp/gui/layer_editor_dialog.py
import os
import shutil
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QMessageBox, QAbstractItemView, QListWidgetItem,
    QLabel, QSpinBox, QFrame, QComboBox, QCheckBox, QFormLayout, QGroupBox  # Added QComboBox, QCheckBox
)
from PySide6.QtGui import QIcon
from .file_dialog_helpers import get_themed_open_filenames
from ..utils.paths import get_media_path, get_media_file_path, get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component
# --- NEW IMPORT ---
from ..text.paragraph_manager import ParagraphManager
# --- END NEW IMPORT ---

logger = logging.getLogger(__name__)

class LayerEditorDialog(QDialog):
    # --- MODIFIED: Added current_text_overlay ---
    def __init__(self, slide_layers, current_duration, current_loop_target,
                 current_text_overlay, # New parameter
                 display_window_instance, parent=None):
        super().__init__(parent)
        logger.debug(f"Initializing LayerEditorDialog. Layers: {len(slide_layers)}, Duration: {current_duration}, Loop: {current_loop_target}, TextOverlay: {current_text_overlay}")
        self.setWindowTitle("Edit Slide Details")
        self.slide_layers = list(slide_layers)
        self.current_duration = current_duration
        self.current_loop_target = current_loop_target
        # --- NEW ATTRIBUTE ---
        self.current_text_overlay = current_text_overlay if current_text_overlay else {} # Ensure it's a dict
        # --- END NEW ATTRIBUTE ---
        self.media_path = get_media_path()
        self.display_window = display_window_instance
        self.setMinimumSize(500, 700) # Increased size a bit

        # --- NEW: Paragraph Manager ---
        self.paragraph_manager = ParagraphManager()
        self.available_paragraphs = [] # To store names
        # --- END NEW ---

        # Set window icon
        try:
            icon_name = "edit.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set LayerEditorDialog window icon: {e}", exc_info=True)

        self.setup_ui()
        self.populate_layers_list()
        self.duration_spinbox.setValue(self.current_duration)
        self.loop_target_spinbox.setValue(self.current_loop_target)
        # --- NEW: Load Text Overlay UI ---
        self.load_text_overlay_ui()
        self.update_text_fields_state() # Initial state update
        # --- END NEW ---
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

        # --- MODIFIED: Group for Timing/Looping ---
        timing_loop_group = QGroupBox("Timing & Looping")
        timing_loop_layout = QFormLayout(timing_loop_group) # Use QFormLayout for label-field pairs

        # Duration/Initial Text Delay Section
        self.duration_label = QLabel("Auto-advance after (seconds, 0 for manual):") # Will change text
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setMinimum(0)
        self.duration_spinbox.setMaximum(3600)
        self.duration_spinbox.setSuffix(" s")
        timing_loop_layout.addRow(self.duration_label, self.duration_spinbox)

        # Loop Section
        loop_label = QLabel("After duration, loop to slide # (1-based, 0 for none):")
        self.loop_target_spinbox = QSpinBox()
        self.loop_target_spinbox.setMinimum(0)
        self.loop_target_spinbox.setMaximum(999)
        self.loop_target_spinbox.setToolTip(
            "Set to 0 for no loop. \n"
            "If > 0, requires duration/delay > 0s on this slide. \n"
            "Looping from the last slide is ignored."
        )
        timing_loop_layout.addRow(loop_label, self.loop_target_spinbox)
        main_layout.addWidget(timing_loop_group)
        # --- END MODIFIED ---

        # --- NEW: Text Overlay Section ---
        text_overlay_group = QGroupBox("Text Overlay")
        text_overlay_layout = QFormLayout(text_overlay_group)

        self.paragraph_combo = QComboBox()
        self.paragraph_combo.addItem("(None)", None) # Default empty option
        self.available_paragraphs = sorted(self.paragraph_manager.list_paragraphs())
        for para_name in self.available_paragraphs:
            self.paragraph_combo.addItem(para_name, para_name)
        self.paragraph_combo.currentIndexChanged.connect(self.update_text_fields_state)
        text_overlay_layout.addRow("Paragraph:", self.paragraph_combo)

        self.start_sentence_spinbox = QSpinBox()
        self.start_sentence_spinbox.setMinimum(1)
        self.start_sentence_spinbox.setMaximum(999) # Adjust if needed
        self.start_sentence_spinbox.valueChanged.connect(self.validate_sentence_range)
        text_overlay_layout.addRow("Start Sentence (1-based):", self.start_sentence_spinbox)

        self.end_sentence_spinbox = QSpinBox()
        self.end_sentence_spinbox.setMinimum(1) # Will be adjusted by validate_sentence_range
        self.end_sentence_spinbox.setMaximum(999)
        self.end_all_checkbox = QCheckBox("Use 'All' Sentences")
        self.end_all_checkbox.toggled.connect(self.update_text_fields_state)
        end_layout = QHBoxLayout()
        end_layout.addWidget(self.end_sentence_spinbox)
        end_layout.addWidget(self.end_all_checkbox)
        text_overlay_layout.addRow("End Sentence (1-based):", end_layout)

        main_layout.addWidget(text_overlay_group)
        # --- END NEW ---

        # Dialog Buttons
        ok_cancel_layout = QHBoxLayout()
        self.preview_button = create_button(
            " Preview Slide", "preview.png", on_click=self.preview_slide_on_display_from_editor
        )
        self.ok_button = create_button("OK", on_click=self.accept_changes)
        self.cancel_button = create_button("Cancel", on_click=self.reject)

        ok_cancel_layout.addWidget(self.preview_button)
        ok_cancel_layout.addStretch()
        ok_cancel_layout.addWidget(self.ok_button)
        ok_cancel_layout.addWidget(self.cancel_button)
        main_layout.addLayout(ok_cancel_layout)
        logger.debug("LayerEditorDialog UI setup complete.")

    # --- NEW METHODS for Text Overlay ---
    def load_text_overlay_ui(self):
        """Populates text overlay UI fields from self.current_text_overlay."""
        para_name = self.current_text_overlay.get("paragraph_name")
        start_sent = self.current_text_overlay.get("start_sentence", 1)
        end_sent = self.current_text_overlay.get("end_sentence", 1)

        if para_name and para_name in self.available_paragraphs:
            self.paragraph_combo.setCurrentText(para_name)
        else:
            self.paragraph_combo.setCurrentIndex(0) # Select "(None)"

        self.start_sentence_spinbox.setValue(start_sent)
        if isinstance(end_sent, str) and end_sent.lower() == "all":
            self.end_all_checkbox.setChecked(True)
            # self.end_sentence_spinbox.setValue(1) # Or some default, it's disabled
        else:
            self.end_all_checkbox.setChecked(False)
            self.end_sentence_spinbox.setValue(end_sent)
        self.validate_sentence_range() # Ensure valid range initially

    def update_text_fields_state(self):
        """Enables/disables text fields based on paragraph selection and 'All' checkbox."""
        paragraph_selected = self.paragraph_combo.currentData() is not None
        use_all_sentences = self.end_all_checkbox.isChecked()

        self.start_sentence_spinbox.setEnabled(paragraph_selected)
        self.end_sentence_spinbox.setEnabled(paragraph_selected and not use_all_sentences)
        self.end_all_checkbox.setEnabled(paragraph_selected)

        if paragraph_selected:
            self.duration_label.setText("Initial Text Delay (seconds, 0 for none):")
            self.duration_spinbox.setToolTip("Delay before the first sentence appears.")
            loaded_para = self.paragraph_manager.load_paragraph(self.paragraph_combo.currentData())
            if loaded_para:
                num_sentences = len(loaded_para.get("sentences", []))
                self.start_sentence_spinbox.setMaximum(max(1,num_sentences)) # Can't be more than available
                if not use_all_sentences:
                    self.end_sentence_spinbox.setMaximum(max(1, num_sentences))
                self.validate_sentence_range()
        else:
            self.duration_label.setText("Auto-advance after (seconds, 0 for manual):")
            self.duration_spinbox.setToolTip("Duration for auto-advancing the slide if no text overlay.")
            # Reset sentence spinboxes if no paragraph
            self.start_sentence_spinbox.setValue(1)
            self.end_sentence_spinbox.setValue(1)
            self.start_sentence_spinbox.setMaximum(999)
            self.end_sentence_spinbox.setMaximum(999)

    def validate_sentence_range(self):
        """Ensures end_sentence is not less than start_sentence."""
        if not self.end_all_checkbox.isChecked():
            start_val = self.start_sentence_spinbox.value()
            end_val = self.end_sentence_spinbox.value()
            self.end_sentence_spinbox.setMinimum(start_val) # End can't be less than start
            if end_val < start_val:
                self.end_sentence_spinbox.setValue(start_val)
    # --- END NEW METHODS ---

    def populate_layers_list(self):
        # ... (This method remains unchanged) ...
        logger.debug("Populating layers list widget.")
        self.layers_list_widget.clear()
        for layer_path in self.slide_layers:
            self.layers_list_widget.addItem(QListWidgetItem(layer_path))
        logger.debug(f"Layers list populated with {len(self.slide_layers)} items.")

    def add_layers(self):
        # ... (This method remains unchanged) ...
        logger.info("Add layers button clicked, opening file dialog.")
        file_names = get_themed_open_filenames(
            self, "Select Image Files to Add as Layers", self.media_path,
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
        )
        if file_names:
            logger.info(f"User selected {len(file_names)} files to add.")
            added_count = 0
            for source_file_path in file_names:
                try:
                    original_filename = os.path.basename(source_file_path)
                    logger.debug(f"Processing selected file: {original_filename} from {source_file_path}")

                    if not is_safe_filename_component(original_filename):
                        logger.warning(f"Unsafe filename skipped: {original_filename}")
                        QMessageBox.warning(self, "Unsafe Filename",
                                            f"The filename '{original_filename}' contains "
                                            f"invalid characters or patterns and cannot be added.")
                        continue

                    dest_path = get_media_file_path(original_filename)
                    final_filename = original_filename

                    if os.path.exists(dest_path) and not os.path.samefile(source_file_path, dest_path):
                        logger.info(f"File '{original_filename}' exists in media directory, attempting to rename.")
                        base_name, extension = os.path.splitext(original_filename)
                        counter = 1
                        while True:
                            final_filename = f"{base_name}_{counter:03d}{extension}"
                            new_dest_path = get_media_file_path(final_filename)
                            if not os.path.exists(new_dest_path):
                                dest_path = new_dest_path
                                break
                            counter += 1
                        logger.info(f"Renamed '{original_filename}' to '{final_filename}' for copy.")

                    if not os.path.exists(dest_path):
                         shutil.copy2(source_file_path, dest_path)
                         logger.info(f"Copied '{source_file_path}' to '{dest_path}'")
                    else:
                         logger.info(f"Using existing file: '{dest_path}' (source was same or already existed)")

                    if final_filename not in self.slide_layers:
                        self.slide_layers.append(final_filename)
                        added_count += 1
                        logger.debug(f"Added '{final_filename}' to slide layers.")
                    else:
                        logger.debug(f"'{final_filename}' already in slide layers.")

                except OSError as e:
                     logger.error(f"OS Error during file check or copy for {source_file_path}: {e}", exc_info=True)
                     QMessageBox.critical(self, "File Check Error", f"Could not check or copy {source_file_path}:\n{e}")

            if added_count > 0:
                logger.info(f"Successfully added {added_count} new layers.")
                self.populate_layers_list()
            else:
                logger.info("No new layers were added from the selection.")
        else:
            logger.info("File dialog cancelled, no files selected.")

    def remove_layer(self):
        # ... (This method remains unchanged) ...
        logger.debug("Remove layer button clicked.")
        current_item = self.layers_list_widget.currentItem()
        if not current_item:
            logger.warning("Attempted to remove layer, but no layer selected.")
            QMessageBox.warning(self, "Remove Layer", "Please select a layer to remove.")
            return
        row = self.layers_list_widget.row(current_item)
        removed_layer = self.slide_layers.pop(row)
        logger.info(f"Removed layer '{removed_layer}' at index {row}.")
        self.populate_layers_list()

    def preview_slide_on_display_from_editor(self):
        logger.debug("Preview slide button clicked.")
        if not self.display_window:
            logger.warning("Preview requested but no display window instance available.")
            return
        self.update_internal_layers_from_widget()
        logger.info(f"Previewing slide with layers: {self.slide_layers}")
        self.display_window.display_images(self.slide_layers)
        # Previewing text from here is tricky, as the text display is tied to ControlWindow state.
        # For now, this only previews images.

    def update_internal_layers_from_widget(self):
        # ... (This method remains unchanged) ...
        logger.debug("Updating internal slide_layers from list widget order.")
        self.slide_layers = [self.layers_list_widget.item(i).text() for i in range(self.layers_list_widget.count())]
        logger.debug(f"Internal layers updated: {self.slide_layers}")

    def accept_changes(self):
        logger.info("OK button clicked, accepting changes.")
        self.update_internal_layers_from_widget() # For image layers
        self.accept()

    # --- MODIFIED: get_updated_slide_data ---
    def get_updated_slide_data(self):
        logger.debug("Getting updated slide data from dialog.")
        data = {
            "layers": self.slide_layers,
            "duration": self.duration_spinbox.value(), # This is now "initial text delay" if text is used
            "loop_to_slide": self.loop_target_spinbox.value(),
            "text_overlay": None # Default to None
        }

        selected_para_name = self.paragraph_combo.currentData()
        if selected_para_name:
            data["text_overlay"] = {
                "paragraph_name": selected_para_name,
                "start_sentence": self.start_sentence_spinbox.value(),
                "end_sentence": "all" if self.end_all_checkbox.isChecked() else self.end_sentence_spinbox.value()
            }
        logger.debug(f"Returning updated slide data: {data}")
        return data
    # --- END MODIFIED ---