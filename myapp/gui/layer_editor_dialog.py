# myapp/gui/layer_editor_dialog.py
import os
import shutil
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QMessageBox, QAbstractItemView, QListWidgetItem,
    QLabel, QSpinBox, QFrame, QComboBox, QCheckBox, QFormLayout, QGroupBox,
    QFontComboBox, QColorDialog, QSlider
)
from PySide6.QtGui import QIcon, QFont, QColor, QPalette
from PySide6.QtCore import Qt

from .file_dialog_helpers import get_themed_open_filenames
from ..utils.paths import get_media_path, get_media_file_path, get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component
from ..text.paragraph_manager import ParagraphManager
# --- NEW IMPORT ---
from ..audio.audio_program_manager import AudioProgramManager
# --- END NEW IMPORT ---
from ..utils.schemas import (
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_FONT_COLOR,
    DEFAULT_BACKGROUND_COLOR, DEFAULT_BACKGROUND_ALPHA,
    DEFAULT_TEXT_ALIGN, DEFAULT_TEXT_VERTICAL_ALIGN, DEFAULT_FIT_TO_WIDTH
)

logger = logging.getLogger(__name__)


class LayerEditorDialog(QDialog):
    def __init__(self, slide_layers, current_duration, current_loop_target,
                 current_text_overlay,
                 current_audio_program_name, current_loop_audio_program,  # --- NEW PARAMS ---
                 display_window_instance, parent=None):
        super().__init__(parent)
        logger.debug(
            f"Initializing LayerEditorDialog. TextOverlay: {current_text_overlay}, AudioProg: {current_audio_program_name}")
        self.setWindowTitle("Edit Slide Details")
        self.slide_layers = list(slide_layers)
        self.current_duration = current_duration
        self.current_loop_target = current_loop_target

        # --- STORE NEW AUDIO PARAMS ---
        self.current_audio_program_name = current_audio_program_name
        self.current_loop_audio_program = current_loop_audio_program
        # --- END NEW AUDIO PARAMS ---

        default_style_base = {
            "font_family": DEFAULT_FONT_FAMILY, "font_size": DEFAULT_FONT_SIZE,
            "font_color": DEFAULT_FONT_COLOR, "background_color": DEFAULT_BACKGROUND_COLOR,
            "background_alpha": DEFAULT_BACKGROUND_ALPHA,
            "text_align": DEFAULT_TEXT_ALIGN,
            "text_vertical_align": DEFAULT_TEXT_VERTICAL_ALIGN,
            "fit_to_width": DEFAULT_FIT_TO_WIDTH,
            "sentence_timing_enabled": False, "auto_advance_slide": False
        }

        if isinstance(current_text_overlay, dict):
            preserved_keys = {
                k: current_text_overlay[k] for k in
                ["paragraph_name", "start_sentence", "end_sentence",
                 "sentence_timing_enabled", "auto_advance_slide"]
                if k in current_text_overlay
            }
            self.current_text_overlay = {**default_style_base, **current_text_overlay, **preserved_keys}
        else:
            self.current_text_overlay = {}

        self.media_path = get_media_path()
        self.display_window = display_window_instance
        self.setMinimumSize(600, 950)  # Increased size slightly more

        self.paragraph_manager = ParagraphManager()
        self.available_paragraphs = []
        # --- NEW: Audio Program Manager ---
        self.audio_program_manager = AudioProgramManager()
        self.available_audio_programs = []
        # --- END NEW ---

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
        self.load_audio_program_ui()  # --- NEW CALL ---
        self.update_text_fields_state()
        self.update_audio_fields_state()  # --- NEW CALL ---
        logger.debug("LayerEditorDialog initialized.")

    # ... (keep _create_color_button, _update_color_button_stylesheet, _handle_font_color_dialog, _handle_bg_color_dialog) ...
    def _create_color_button(self, initial_color_hex, on_click_method):
        button = QPushButton()
        button.setFixedSize(30, 30)
        button.clicked.connect(on_click_method)
        self._update_color_button_stylesheet(button, initial_color_hex)
        return button

    def _update_color_button_stylesheet(self, button, color_hex):
        button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid gray;")
        button.setProperty("color_hex", color_hex)

    def _handle_font_color_dialog(self):
        current_color_hex = self.font_color_button.property("color_hex")
        color = QColorDialog.getColor(QColor(current_color_hex), self, "Select Font Color")
        if color.isValid():
            self._update_color_button_stylesheet(self.font_color_button, color.name())

    def _handle_bg_color_dialog(self):
        current_color_hex = self.bg_color_button.property("color_hex")
        color = QColorDialog.getColor(QColor(current_color_hex), self, "Select Background Color")
        if color.isValid():
            self._update_color_button_stylesheet(self.bg_color_button, color.name())

    def setup_ui(self):
        logger.debug("Setting up LayerEditorDialog UI...")
        main_layout = QVBoxLayout(self)

        layers_group = QGroupBox("Image Layers")
        layers_layout = QVBoxLayout(layers_group)
        layers_layout.addWidget(QLabel("Image Layers (drag to reorder):"))
        self.layers_list_widget = QListWidget()
        self.layers_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        layers_layout.addWidget(self.layers_list_widget)
        layers_buttons_layout = QHBoxLayout()
        self.add_layer_button = create_button(" Add Image(s)", "add.png", on_click=self.add_layers)
        self.remove_layer_button = create_button(" Remove Selected", "remove.png", on_click=self.remove_layer)
        layers_buttons_layout.addWidget(self.add_layer_button);
        layers_buttons_layout.addWidget(self.remove_layer_button)
        layers_layout.addLayout(layers_buttons_layout);
        main_layout.addWidget(layers_group)

        timing_loop_group = QGroupBox("Timing & Looping (for Slide Advance / Text Delay)")
        timing_loop_layout = QFormLayout(timing_loop_group)
        self.duration_label = QLabel("Initial Text Delay / Slide Duration (s):")
        self.duration_spinbox = QSpinBox();
        self.duration_spinbox.setRange(0, 3600);
        self.duration_spinbox.setSuffix(" s")
        timing_loop_layout.addRow(self.duration_label, self.duration_spinbox)
        loop_label = QLabel("After duration, loop to slide # (1-based, 0 for none):")
        self.loop_target_spinbox = QSpinBox();
        self.loop_target_spinbox.setRange(0, 999)
        timing_loop_layout.addRow(loop_label, self.loop_target_spinbox);
        main_layout.addWidget(timing_loop_group)

        # Text Overlay Group
        text_overlay_group = QGroupBox("Text Overlay Settings")
        text_overlay_form_layout = QFormLayout(text_overlay_group)
        self.paragraph_combo = QComboBox()
        self.paragraph_combo.addItem("(None)", None)
        self.available_paragraphs = sorted(self.paragraph_manager.list_paragraphs())
        for para_name in self.available_paragraphs:
            self.paragraph_combo.addItem(para_name, para_name)
        self.paragraph_combo.currentIndexChanged.connect(self.update_text_fields_state)
        text_overlay_form_layout.addRow("Paragraph:", self.paragraph_combo)
        self.start_sentence_spinbox = QSpinBox();
        self.start_sentence_spinbox.setRange(1, 999)
        self.start_sentence_spinbox.valueChanged.connect(self.validate_sentence_range)
        text_overlay_form_layout.addRow("Start Sentence (1-based):", self.start_sentence_spinbox)
        end_layout = QHBoxLayout()
        self.end_sentence_spinbox = QSpinBox();
        self.end_sentence_spinbox.setRange(1, 999)
        self.end_all_checkbox = QCheckBox("Use 'All' Sentences")
        self.end_all_checkbox.toggled.connect(self.update_text_fields_state)
        end_layout.addWidget(self.end_sentence_spinbox);
        end_layout.addWidget(self.end_all_checkbox)
        text_overlay_form_layout.addRow("End Sentence (1-based):", end_layout)
        self.sentence_timing_check = QCheckBox("Enable Sentence Timers")
        self.sentence_timing_check.toggled.connect(self.update_text_fields_state)
        text_overlay_form_layout.addRow("", self.sentence_timing_check)
        self.auto_advance_slide_check = QCheckBox("Auto-Advance to Next Slide (after text)")
        text_overlay_form_layout.addRow("", self.auto_advance_slide_check)
        text_overlay_form_layout.addRow(QLabel("--- Text Style ---"))
        self.font_combo = QFontComboBox()
        text_overlay_form_layout.addRow("Font Family:", self.font_combo)
        self.font_size_spinbox = QSpinBox();
        self.font_size_spinbox.setRange(8, 200);
        self.font_size_spinbox.setSuffix(" pt")
        text_overlay_form_layout.addRow("Font Size:", self.font_size_spinbox)
        self.font_color_button = self._create_color_button(DEFAULT_FONT_COLOR, self._handle_font_color_dialog)
        text_overlay_form_layout.addRow("Font Color:", self.font_color_button)
        self.bg_color_button = self._create_color_button(DEFAULT_BACKGROUND_COLOR, self._handle_bg_color_dialog)
        text_overlay_form_layout.addRow("Background Color:", self.bg_color_button)
        bg_alpha_layout = QHBoxLayout()
        self.bg_alpha_slider = QSlider(Qt.Orientation.Horizontal);
        self.bg_alpha_slider.setRange(0, 9)
        self.bg_alpha_label = QLabel(f"Opacity: {self.bg_alpha_slider.value()}")
        self.bg_alpha_slider.valueChanged.connect(
            lambda val: self.bg_alpha_label.setText(f"Opacity: {val} ({((9 - val) / 9.0 * 100):.0f}% solid)"))
        bg_alpha_layout.addWidget(self.bg_alpha_slider);
        bg_alpha_layout.addWidget(self.bg_alpha_label)
        text_overlay_form_layout.addRow("Background Transparency:", bg_alpha_layout)
        self.text_align_combo = QComboBox();
        self.text_align_combo.addItems(["left", "center", "right"])
        text_overlay_form_layout.addRow("Horiz. Align:", self.text_align_combo)
        self.text_valign_combo = QComboBox();
        self.text_valign_combo.addItems(["top", "middle", "bottom"])
        text_overlay_form_layout.addRow("Vert. Position:", self.text_valign_combo)
        self.fit_to_width_check = QCheckBox("Fit Background to Screen Width")
        text_overlay_form_layout.addRow("", self.fit_to_width_check)
        main_layout.addWidget(text_overlay_group)

        # --- NEW AUDIO PROGRAM GROUP ---
        audio_program_group = QGroupBox("Audio Program Settings")
        audio_program_form_layout = QFormLayout(audio_program_group)
        self.audio_program_combo = QComboBox()
        self.audio_program_combo.addItem("(None)", None)  # UserRole is None
        self.available_audio_programs = sorted(self.audio_program_manager.list_programs())
        for prog_name in self.available_audio_programs:
            self.audio_program_combo.addItem(prog_name, prog_name)  # UserRole is program name
        self.audio_program_combo.currentIndexChanged.connect(self.update_audio_fields_state)
        audio_program_form_layout.addRow("Audio Program:", self.audio_program_combo)
        self.loop_audio_checkbox = QCheckBox("Loop Audio Program on this Slide")
        audio_program_form_layout.addRow("", self.loop_audio_checkbox)
        main_layout.addWidget(audio_program_group)
        # --- END NEW AUDIO PROGRAM GROUP ---

        ok_cancel_layout = QHBoxLayout()
        self.preview_button = create_button(" Preview Slide Images", "preview.png",
                                            on_click=self.preview_slide_on_display_from_editor)
        self.ok_button = create_button("OK", on_click=self.accept_changes)
        self.cancel_button = create_button("Cancel", on_click=self.reject)
        ok_cancel_layout.addWidget(self.preview_button);
        ok_cancel_layout.addStretch()
        ok_cancel_layout.addWidget(self.ok_button);
        ok_cancel_layout.addWidget(self.cancel_button)
        main_layout.addLayout(ok_cancel_layout)
        logger.debug("LayerEditorDialog UI setup complete.")

    def load_text_overlay_ui(self):
        overlay = self.current_text_overlay
        para_name = overlay.get("paragraph_name")
        if para_name and para_name in self.available_paragraphs:
            self.paragraph_combo.setCurrentText(para_name)
        elif para_name:
            self.paragraph_combo.addItem(f"{para_name} (Missing!)")
            self.paragraph_combo.setCurrentText(f"{para_name} (Missing!)")
            logger.warning(f"Paragraph '{para_name}' from playlist not found.")
        else:
            self.paragraph_combo.setCurrentIndex(0)

        self.start_sentence_spinbox.setValue(overlay.get("start_sentence", 1))
        end_sent = overlay.get("end_sentence", 1)
        if isinstance(end_sent, str) and end_sent.lower() == "all":
            self.end_all_checkbox.setChecked(True);
            self.end_sentence_spinbox.setValue(1)
        else:
            self.end_all_checkbox.setChecked(False);
            self.end_sentence_spinbox.setValue(int(end_sent))

        self.sentence_timing_check.setChecked(overlay.get("sentence_timing_enabled", False))
        self.auto_advance_slide_check.setChecked(overlay.get("auto_advance_slide", False))
        self.font_combo.setCurrentFont(QFont(overlay.get("font_family", DEFAULT_FONT_FAMILY)))
        self.font_size_spinbox.setValue(overlay.get("font_size", DEFAULT_FONT_SIZE))
        self._update_color_button_stylesheet(self.font_color_button, overlay.get("font_color", DEFAULT_FONT_COLOR))
        self._update_color_button_stylesheet(self.bg_color_button,
                                             overlay.get("background_color", DEFAULT_BACKGROUND_COLOR))
        alpha_255 = overlay.get("background_alpha", DEFAULT_BACKGROUND_ALPHA)
        slider_val = round(9 * (1 - alpha_255 / 255.0)) if alpha_255 < 255 else 0
        self.bg_alpha_slider.setValue(max(0, min(9, slider_val)))
        self.bg_alpha_label.setText(
            f"Opacity: {self.bg_alpha_slider.value()} ({((9 - self.bg_alpha_slider.value()) / 9.0 * 100):.0f}% solid)")
        self.text_align_combo.setCurrentText(overlay.get("text_align", DEFAULT_TEXT_ALIGN))
        self.text_valign_combo.setCurrentText(overlay.get("text_vertical_align", DEFAULT_TEXT_VERTICAL_ALIGN))
        self.fit_to_width_check.setChecked(overlay.get("fit_to_width", DEFAULT_FIT_TO_WIDTH))
        self.validate_sentence_range()

    # --- NEW METHOD TO LOAD AUDIO UI ---
    def load_audio_program_ui(self):
        logger.debug(
            f"Loading audio UI. Program: '{self.current_audio_program_name}', Loop: {self.current_loop_audio_program}")
        if self.current_audio_program_name and self.current_audio_program_name in self.available_audio_programs:
            self.audio_program_combo.setCurrentText(self.current_audio_program_name)
        elif self.current_audio_program_name:  # Program name exists in data but not in current list
            self.audio_program_combo.addItem(f"{self.current_audio_program_name} (Missing!)")
            self.audio_program_combo.setCurrentText(f"{self.current_audio_program_name} (Missing!)")
            logger.warning(f"Audio program '{self.current_audio_program_name}' from playlist not found.")
        else:
            self.audio_program_combo.setCurrentIndex(0)  # Select "(None)"

        self.loop_audio_checkbox.setChecked(self.current_loop_audio_program)

    # --- END NEW METHOD ---

    def update_text_fields_state(self):
        selected_paragraph_data = self.paragraph_combo.currentData()
        paragraph_genuinely_selected = selected_paragraph_data is not None and \
                                       not str(self.paragraph_combo.currentText()).endswith("(Missing!)")
        use_all_sentences = self.end_all_checkbox.isChecked()
        sentence_timing_on = self.sentence_timing_check.isChecked()

        self.start_sentence_spinbox.setEnabled(paragraph_genuinely_selected)
        self.end_sentence_spinbox.setEnabled(paragraph_genuinely_selected and not use_all_sentences)
        self.end_all_checkbox.setEnabled(paragraph_genuinely_selected)
        self.sentence_timing_check.setEnabled(paragraph_genuinely_selected)
        self.auto_advance_slide_check.setEnabled(paragraph_genuinely_selected and sentence_timing_on)

        style_fields_enabled = paragraph_genuinely_selected
        self.font_combo.setEnabled(style_fields_enabled)
        self.font_size_spinbox.setEnabled(style_fields_enabled)
        # ... (rest of text style fields enablement) ...
        self.font_color_button.setEnabled(style_fields_enabled)
        self.bg_color_button.setEnabled(style_fields_enabled)
        self.bg_alpha_slider.setEnabled(style_fields_enabled)
        self.text_align_combo.setEnabled(style_fields_enabled)
        self.text_valign_combo.setEnabled(style_fields_enabled)
        self.fit_to_width_check.setEnabled(style_fields_enabled)

        if paragraph_genuinely_selected:
            self.duration_label.setText("Initial Text Delay (s, 0 for none):")
            loaded_para = self.paragraph_manager.load_paragraph(selected_paragraph_data)
            if loaded_para:
                num_sentences = len(loaded_para.get("sentences", []))
                self.start_sentence_spinbox.setMaximum(max(1, num_sentences))
                if not use_all_sentences: self.end_sentence_spinbox.setMaximum(max(1, num_sentences))
                self.validate_sentence_range()
        else:
            self.duration_label.setText("Slide Duration (s, 0 for manual):")
            # ... (reset text style fields if no valid paragraph) ...
            if not style_fields_enabled:
                self.font_combo.setCurrentFont(QFont(DEFAULT_FONT_FAMILY))
                self.font_size_spinbox.setValue(DEFAULT_FONT_SIZE)
                self._update_color_button_stylesheet(self.font_color_button, DEFAULT_FONT_COLOR)
                self._update_color_button_stylesheet(self.bg_color_button, DEFAULT_BACKGROUND_COLOR)
                self.bg_alpha_slider.setValue(round(9 * (1 - DEFAULT_BACKGROUND_ALPHA / 255.0)))
                self.text_align_combo.setCurrentText(DEFAULT_TEXT_ALIGN)
                self.text_valign_combo.setCurrentText(DEFAULT_TEXT_VERTICAL_ALIGN)
                self.fit_to_width_check.setChecked(DEFAULT_FIT_TO_WIDTH)

    # --- NEW METHOD TO UPDATE AUDIO FIELDS STATE ---
    def update_audio_fields_state(self):
        selected_audio_program_data = self.audio_program_combo.currentData()  # This is program name or None
        audio_program_genuinely_selected = selected_audio_program_data is not None and \
                                           not str(self.audio_program_combo.currentText()).endswith("(Missing!)")
        self.loop_audio_checkbox.setEnabled(audio_program_genuinely_selected)
        if not audio_program_genuinely_selected:
            self.loop_audio_checkbox.setChecked(False)

    # --- END NEW METHOD ---

    def validate_sentence_range(self):
        if not self.end_all_checkbox.isChecked():
            start_val = self.start_sentence_spinbox.value()
            self.end_sentence_spinbox.setMinimum(start_val)
            if self.end_sentence_spinbox.value() < start_val:
                self.end_sentence_spinbox.setValue(start_val)

    # ... (keep populate_layers_list, add_layers, remove_layer, preview_slide_on_display_from_editor, update_internal_layers_from_widget, accept_changes)
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
                QMessageBox.warning(self, "Unsafe Filename", f"Skipped: {filename}");
                continue
            dest_path = get_media_file_path(filename);
            final_filename = filename
            if os.path.exists(dest_path) and not os.path.samefile(source_path, dest_path):
                base, ext = os.path.splitext(filename);
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
        self.slide_layers.pop(row);
        self.populate_layers_list()

    def preview_slide_on_display_from_editor(self):
        if not self.display_window: return
        self.update_internal_layers_from_widget()
        # Clear text for image-only preview, and also clear any audio from display window context
        self.display_window.current_text = None
        if hasattr(self.display_window, 'slide_audio_player') and self.display_window.slide_audio_player:
            self.display_window.slide_audio_player.stop()
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
            "text_overlay": None,
            # --- NEW: Get audio settings ---
            "audio_program_name": None,
            "loop_audio_program": False
            # --- END NEW ---
        }
        selected_paragraph_data = self.paragraph_combo.currentData()
        if selected_paragraph_data and not str(self.paragraph_combo.currentText()).endswith("(Missing!)"):
            slider_val = self.bg_alpha_slider.value()
            alpha_val_from_slider = max(0, min(255, 255 - (slider_val * 25)))
            data["text_overlay"] = {
                "paragraph_name": selected_paragraph_data,
                "start_sentence": self.start_sentence_spinbox.value(),
                "end_sentence": "all" if self.end_all_checkbox.isChecked() else self.end_sentence_spinbox.value(),
                "sentence_timing_enabled": self.sentence_timing_check.isChecked(),
                "auto_advance_slide": self.auto_advance_slide_check.isChecked(),
                "font_family": self.font_combo.currentFont().family(),
                "font_size": self.font_size_spinbox.value(),
                "font_color": self.font_color_button.property("color_hex"),
                "background_color": self.bg_color_button.property("color_hex"),
                "background_alpha": alpha_val_from_slider,
                "text_align": self.text_align_combo.currentText(),
                "text_vertical_align": self.text_valign_combo.currentText(),
                "fit_to_width": self.fit_to_width_check.isChecked()
            }

        # --- NEW: Populate audio settings in returned data ---
        selected_audio_program = self.audio_program_combo.currentData()  # This is the program name or None
        if selected_audio_program and not str(self.audio_program_combo.currentText()).endswith("(Missing!)"):
            data["audio_program_name"] = selected_audio_program
            data["loop_audio_program"] = self.loop_audio_checkbox.isChecked()
        # --- END NEW ---

        logger.debug(f"Returning updated slide data: {data}")
        return data