# myapp/gui/layer_editor_dialog.py
import os
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QFileDialog, QMessageBox, QAbstractItemView, QListWidgetItem,
    QLabel, QSpinBox, QFrame # Added QFrame for visual separation
)
from PySide6.QtGui import QIcon
from ..utils.paths import get_media_path, get_icon_file_path

class LayerEditorDialog(QDialog):
    # MODIFIED: Now takes current_loop_target
    def __init__(self, slide_layers, current_duration, current_loop_target, display_window_instance, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Slide Details") # More generic title
        self.slide_layers = list(slide_layers)
        self.current_duration = current_duration
        self.current_loop_target = current_loop_target # Store loop target
        self.media_path = get_media_path()
        self.display_window = display_window_instance
        self.setMinimumSize(400, 600) # Increased height for loop option

        self.setup_ui()
        self.populate_layers_list()
        self.duration_spinbox.setValue(self.current_duration)
        self.loop_target_spinbox.setValue(self.current_loop_target) # Set initial loop target

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Layers Management
        layers_label = QLabel("Image Layers (drag to reorder):")
        main_layout.addWidget(layers_label)
        self.layers_list_widget = QListWidget()
        self.layers_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        main_layout.addWidget(self.layers_list_widget)

        layers_buttons_layout = QHBoxLayout()
        self.add_layer_button = QPushButton(" Add Image(s)")
        self.remove_layer_button = QPushButton(" Remove Selected")
        self.add_layer_button.setIcon(QIcon(get_icon_file_path("add.png")))
        self.remove_layer_button.setIcon(QIcon(get_icon_file_path("remove.png")))
        self.add_layer_button.clicked.connect(self.add_layers)
        self.remove_layer_button.clicked.connect(self.remove_layer)
        layers_buttons_layout.addWidget(self.add_layer_button)
        layers_buttons_layout.addWidget(self.remove_layer_button)
        main_layout.addLayout(layers_buttons_layout)

        # Separator
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line1)

        # Duration Setting
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Auto-advance after (seconds, 0 for manual):")
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setMinimum(0)
        self.duration_spinbox.setMaximum(3600)
        self.duration_spinbox.setSuffix(" s")
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_spinbox)
        main_layout.addLayout(duration_layout)

        # --- NEW: Loop Target Editor ---
        loop_layout = QHBoxLayout()
        loop_label = QLabel("After duration, loop to slide # (1-based, 0 for none):")
        self.loop_target_spinbox = QSpinBox()
        self.loop_target_spinbox.setMinimum(0) # 0 for no loop
        self.loop_target_spinbox.setMaximum(999) # Max 999 slides, adjust as needed
        self.loop_target_spinbox.setToolTip(
            "Set to 0 for no loop. \n"
            "If > 0, requires duration > 0s on this slide. \n"
            "Looping from the last slide is ignored."
            )
        loop_layout.addWidget(loop_label)
        loop_layout.addWidget(self.loop_target_spinbox)
        main_layout.addLayout(loop_layout)
        # --- END NEW ---

        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line2)

        # Dialog Buttons (Preview, OK, Cancel)
        ok_cancel_layout = QHBoxLayout()
        self.preview_button = QPushButton(" Preview Slide")
        self.preview_button.setIcon(QIcon(get_icon_file_path("preview.png")))
        self.preview_button.clicked.connect(self.preview_slide_on_display_from_editor)

        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept_changes)
        self.cancel_button.clicked.connect(self.reject)

        ok_cancel_layout.addWidget(self.preview_button)
        ok_cancel_layout.addStretch()
        ok_cancel_layout.addWidget(self.ok_button)
        ok_cancel_layout.addWidget(self.cancel_button)
        main_layout.addLayout(ok_cancel_layout)

    def populate_layers_list(self):
        # ... (as before) ...
        self.layers_list_widget.clear()
        for layer_path in self.slide_layers:
            self.layers_list_widget.addItem(QListWidgetItem(layer_path))

    def add_layers(self):
        # ... (as before, handling file copying and renaming) ...
        file_names, _ = QFileDialog.getOpenFileNames(
            self, "Select Image Files to Add as Layers", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
        )
        if file_names:
            for source_file_path in file_names:
                try:
                    original_filename = os.path.basename(source_file_path)
                    dest_path = os.path.join(self.media_path, original_filename)
                    final_filename = original_filename
                    if os.path.exists(dest_path) and not os.path.samefile(source_file_path, dest_path):
                        base_name, extension = os.path.splitext(original_filename)
                        counter = 1
                        while True:
                            final_filename = f"{base_name}_{counter:03d}{extension}"
                            new_dest_path = os.path.join(self.media_path, final_filename)
                            if not os.path.exists(new_dest_path):
                                dest_path = new_dest_path
                                break
                            counter += 1
                        print(f"Info: '{original_filename}' exists, renaming to '{final_filename}' for copy.")
                    if not os.path.exists(dest_path):
                         shutil.copy2(source_file_path, dest_path)
                         print(f"Copied '{source_file_path}' to '{dest_path}'")
                    else:
                         print(f"Using existing file: '{dest_path}'")
                    if final_filename not in self.slide_layers:
                        self.slide_layers.append(final_filename)
                except OSError as e:
                     QMessageBox.critical(self, "File Check Error", f"Could not check or copy {source_file_path}:\n{e}")
                except Exception as e:
                    QMessageBox.critical(self, "File Copy Error", f"Could not process {source_file_path}:\n{e}")
            self.populate_layers_list()


    def remove_layer(self):
        # ... (as before) ...
        current_item = self.layers_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Remove Layer", "Please select a layer to remove.")
            return
        row = self.layers_list_widget.row(current_item)
        del self.slide_layers[row]
        self.populate_layers_list()


    def preview_slide_on_display_from_editor(self):
        # ... (as before) ...
        if not self.display_window: return
        self.update_internal_layers_from_widget()
        self.display_window.display_images(self.slide_layers, self.media_path)


    def update_internal_layers_from_widget(self):
        # ... (as before) ...
        self.slide_layers = [self.layers_list_widget.item(i).text() for i in range(self.layers_list_widget.count())]


    def accept_changes(self):
        # ... (as before) ...
        self.update_internal_layers_from_widget()
        self.accept()


    # --- MODIFIED: Return layers, duration, and loop_target ---
    def get_updated_slide_data(self):
        return {
            "layers": self.slide_layers,
            "duration": self.duration_spinbox.value(),
            "loop_to_slide": self.loop_target_spinbox.value() # Get loop target
        }
    # --- END MODIFIED ---