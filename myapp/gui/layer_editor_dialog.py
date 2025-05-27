# myapp/gui/layer_editor_dialog.py
import os
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QFileDialog, QMessageBox, QAbstractItemView, QListWidgetItem,
    QLabel, QSpinBox, QFrame
)
from PySide6.QtGui import QIcon
# --- MODIFIED: Added get_media_file_path ---
from ..utils.paths import get_media_path, get_media_file_path
# --- END MODIFIED ---
from .widget_helpers import create_button

class LayerEditorDialog(QDialog):
    def __init__(self, slide_layers, current_duration, current_loop_target, display_window_instance, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Slide Details")
        self.slide_layers = list(slide_layers)
        self.current_duration = current_duration
        self.current_loop_target = current_loop_target
        self.media_path = get_media_path() # Keep for base path needs
        self.display_window = display_window_instance
        self.setMinimumSize(400, 600)

        self.setup_ui()
        self.populate_layers_list()
        self.duration_spinbox.setValue(self.current_duration)
        self.loop_target_spinbox.setValue(self.current_loop_target)

    def setup_ui(self):
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

    def populate_layers_list(self):
        self.layers_list_widget.clear()
        for layer_path in self.slide_layers:
            self.layers_list_widget.addItem(QListWidgetItem(layer_path))

    def add_layers(self):
        file_names, _ = QFileDialog.getOpenFileNames(
            self, "Select Image Files to Add as Layers", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
        )
        if file_names:
            for source_file_path in file_names:
                try:
                    original_filename = os.path.basename(source_file_path)
                    # --- MODIFIED: Use get_media_file_path ---
                    dest_path = get_media_file_path(original_filename)
                    # --- END MODIFIED ---
                    final_filename = original_filename

                    # Handle renaming if file exists but isn't the same file
                    if os.path.exists(dest_path) and not os.path.samefile(source_file_path, dest_path):
                        base_name, extension = os.path.splitext(original_filename)
                        counter = 1
                        while True:
                            final_filename = f"{base_name}_{counter:03d}{extension}"
                            # --- MODIFIED: Use get_media_file_path ---
                            new_dest_path = get_media_file_path(final_filename)
                            # --- END MODIFIED ---
                            if not os.path.exists(new_dest_path):
                                dest_path = new_dest_path
                                break
                            counter += 1
                        print(f"Info: '{original_filename}' exists, renaming to '{final_filename}' for copy.")

                    # Copy if it doesn't exist yet
                    if not os.path.exists(dest_path):
                         shutil.copy2(source_file_path, dest_path)
                         print(f"Copied '{source_file_path}' to '{dest_path}'")
                    else:
                         print(f"Using existing file: '{dest_path}'")

                    # Add to layers list if not already there
                    if final_filename not in self.slide_layers:
                        self.slide_layers.append(final_filename)

                except OSError as e:
                     QMessageBox.critical(self, "File Check Error", f"Could not check or copy {source_file_path}:\n{e}")
                except Exception as e:
                    QMessageBox.critical(self, "File Copy Error", f"Could not process {source_file_path}:\n{e}")
            self.populate_layers_list()


    def remove_layer(self):
        current_item = self.layers_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Remove Layer", "Please select a layer to remove.")
            return
        row = self.layers_list_widget.row(current_item)
        del self.slide_layers[row]
        self.populate_layers_list()


    def preview_slide_on_display_from_editor(self):
        if not self.display_window: return
        self.update_internal_layers_from_widget()
        # --- MODIFIED: Pass only filenames, display_images will use helpers ---
        self.display_window.display_images(self.slide_layers) #
        # --- END MODIFIED ---


    def update_internal_layers_from_widget(self):
        self.slide_layers = [self.layers_list_widget.item(i).text() for i in range(self.layers_list_widget.count())]


    def accept_changes(self):
        self.update_internal_layers_from_widget()
        self.accept()


    def get_updated_slide_data(self):
        return {
            "layers": self.slide_layers,
            "duration": self.duration_spinbox.value(),
            "loop_to_slide": self.loop_target_spinbox.value()
        }