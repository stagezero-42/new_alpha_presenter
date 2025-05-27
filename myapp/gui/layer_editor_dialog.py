# myapp/gui/layer_editor_dialog.py
import os
import shutil
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QMessageBox, QAbstractItemView, QListWidgetItem,
    QLabel, QSpinBox, QFrame
)
from PySide6.QtGui import QIcon
# --- MODIFIED: Import new helper ---
from .file_dialog_helpers import get_themed_open_filenames
# --- END MODIFIED ---
from ..utils.paths import get_media_path, get_media_file_path, get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)

class LayerEditorDialog(QDialog):
    def __init__(self, slide_layers, current_duration, current_loop_target, display_window_instance, parent=None):
        super().__init__(parent)
        logger.debug(f"Initializing LayerEditorDialog for slide with {len(slide_layers)} layers, duration {current_duration}, loop {current_loop_target}.")
        self.setWindowTitle("Edit Slide Details")
        self.slide_layers = list(slide_layers)
        self.current_duration = current_duration
        self.current_loop_target = current_loop_target
        self.media_path = get_media_path()
        self.display_window = display_window_instance
        self.setMinimumSize(400, 600)

        # --- ADD THIS CODE ---
        try:
            icon_name = "edit.png" # Edit icon
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logger.debug(f"Set window icon for LayerEditorDialog from: {icon_path}")
            else:
                logger.warning(f"LayerEditorDialog icon '{icon_name}' not found.")
        except Exception as e:
            logger.error(f"Failed to set LayerEditorDialog window icon: {e}", exc_info=True)
        # --- END OF ADDED CODE ---

        self.setup_ui()
        self.populate_layers_list()
        self.duration_spinbox.setValue(self.current_duration)
        self.loop_target_spinbox.setValue(self.current_loop_target)
        logger.debug("LayerEditorDialog initialized.")

    def setup_ui(self):
        logger.debug("Setting up LayerEditorDialog UI...")
        main_layout = QVBoxLayout(self)

        layers_label = QLabel("Image Layers (drag to reorder):")
        main_layout.addWidget(layers_label)
        self.layers_list_widget = QListWidget()
        self.layers_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        main_layout.addWidget(self.layers_list_widget)

        layers_buttons_layout = QHBoxLayout()
        self.add_layer_button = create_button(" Add Image(s)", "add.png", on_click=self.add_layers)
        self.remove_layer_button = create_button(" Remove Selected", "remove.png", on_click=self.remove_layer)
        layers_buttons_layout.addWidget(self.add_layer_button)
        layers_buttons_layout.addWidget(self.remove_layer_button)
        main_layout.addLayout(layers_buttons_layout)

        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line1)

        duration_layout = QHBoxLayout()
        duration_label = QLabel("Auto-advance after (seconds, 0 for manual):")
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setMinimum(0)
        self.duration_spinbox.setMaximum(3600)
        self.duration_spinbox.setSuffix(" s")
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_spinbox)
        main_layout.addLayout(duration_layout)

        loop_layout = QHBoxLayout()
        loop_label = QLabel("After duration, loop to slide # (1-based, 0 for none):")
        self.loop_target_spinbox = QSpinBox()
        self.loop_target_spinbox.setMinimum(0)
        self.loop_target_spinbox.setMaximum(999)
        self.loop_target_spinbox.setToolTip(
            "Set to 0 for no loop. \n"
            "If > 0, requires duration > 0s on this slide. \n"
            "Looping from the last slide is ignored."
        )
        loop_layout.addWidget(loop_label)
        loop_layout.addWidget(self.loop_target_spinbox)
        main_layout.addLayout(loop_layout)

        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line2)

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

    def populate_layers_list(self):
        logger.debug("Populating layers list widget.")
        self.layers_list_widget.clear()
        for layer_path in self.slide_layers:
            self.layers_list_widget.addItem(QListWidgetItem(layer_path))
        logger.debug(f"Layers list populated with {len(self.slide_layers)} items.")

    def add_layers(self):
        logger.info("Add layers button clicked, opening file dialog.")
        # --- MODIFIED: Use new helper ---
        file_names = get_themed_open_filenames(
            self, "Select Image Files to Add as Layers", self.media_path,
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
        )
        # --- END MODIFIED ---

        if file_names: # file_names is now a list
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
                except Exception as e:
                    logger.error(f"Generic error processing file {source_file_path}: {e}", exc_info=True)
                    QMessageBox.critical(self, "File Copy Error", f"Could not process {source_file_path}:\n{e}")

            if added_count > 0:
                logger.info(f"Successfully added {added_count} new layers.")
                self.populate_layers_list()
            else:
                logger.info("No new layers were added from the selection.")
        else:
            logger.info("File dialog cancelled, no files selected.")


    def remove_layer(self):
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


    def update_internal_layers_from_widget(self):
        logger.debug("Updating internal slide_layers from list widget order.")
        self.slide_layers = [self.layers_list_widget.item(i).text() for i in range(self.layers_list_widget.count())]
        logger.debug(f"Internal layers updated: {self.slide_layers}")


    def accept_changes(self):
        logger.info("OK button clicked, accepting changes.")
        self.update_internal_layers_from_widget()
        self.accept()


    def get_updated_slide_data(self):
        logger.debug("Getting updated slide data from dialog.")
        data = {
            "layers": self.slide_layers,
            "duration": self.duration_spinbox.value(),
            "loop_to_slide": self.loop_target_spinbox.value()
        }
        logger.debug(f"Returning updated slide data: {data}")
        return data