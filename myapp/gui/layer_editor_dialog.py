# myapp/gui/layer_editor_dialog.py
import os
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QFileDialog, QMessageBox, QAbstractItemView, QListWidgetItem
)
from PySide6.QtGui import QIcon
from ..utils.paths import get_media_path, get_icon_file_path

class LayerEditorDialog(QDialog):
    def __init__(self, slide_layers, display_window_instance, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Slide Layers")
        self.slide_layers = list(slide_layers)  # Work on a copy
        self.media_path = get_media_path()  # Use central media path
        self.display_window = display_window_instance
        self.setMinimumSize(400, 500)

        self.setup_ui()
        self.populate_layers_list()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        self.layers_list_widget = QListWidget()
        self.layers_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        main_layout.addWidget(self.layers_list_widget)

        buttons_layout = QHBoxLayout()
        self.add_layer_button = QPushButton(" Add Image(s)")
        self.remove_layer_button = QPushButton(" Remove Selected")
        self.preview_button = QPushButton(" Preview Slide")

        self.add_layer_button.setIcon(QIcon(get_icon_file_path("add.png")))
        self.remove_layer_button.setIcon(QIcon(get_icon_file_path("remove.png")))
        self.preview_button.setIcon(QIcon(get_icon_file_path("preview.png")))

        self.add_layer_button.clicked.connect(self.add_layers)
        self.remove_layer_button.clicked.connect(self.remove_layer)
        self.preview_button.clicked.connect(self.preview_slide_on_display)

        buttons_layout.addWidget(self.add_layer_button)
        buttons_layout.addWidget(self.remove_layer_button)
        buttons_layout.addWidget(self.preview_button)
        main_layout.addLayout(buttons_layout)

        ok_cancel_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        ok_cancel_layout.addStretch()
        ok_cancel_layout.addWidget(self.ok_button)
        ok_cancel_layout.addWidget(self.cancel_button)
        self.ok_button.clicked.connect(self.accept_changes)
        self.cancel_button.clicked.connect(self.reject)
        main_layout.addLayout(ok_cancel_layout)

    def populate_layers_list(self):
        self.layers_list_widget.clear()
        for layer_path in self.slide_layers:
            self.layers_list_widget.addItem(QListWidgetItem(layer_path))

    # --- MODIFIED FUNCTION ---
    def add_layers(self):
        """Adds layers, copying files and renaming if necessary."""
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

                    # Check if a file with this name exists AND it's not the exact same file
                    if os.path.exists(dest_path) and not os.path.samefile(source_file_path, dest_path):
                        base_name, extension = os.path.splitext(original_filename)
                        counter = 1
                        while True:
                            # Create new name: base_001.ext
                            final_filename = f"{base_name}_{counter:03d}{extension}"
                            new_dest_path = os.path.join(self.media_path, final_filename)
                            if not os.path.exists(new_dest_path):
                                dest_path = new_dest_path # Found an unused name
                                break
                            counter += 1
                        print(f"Info: '{original_filename}' exists, renaming to '{final_filename}' for copy.")

                    # Copy only if the final destination doesn't exist (it won't if renamed)
                    # or if it was the *same* file (in which case we don't copy, just use existing)
                    if not os.path.exists(dest_path):
                         shutil.copy2(source_file_path, dest_path)
                         print(f"Copied '{source_file_path}' to '{dest_path}'")
                    else:
                         # This happens if the file exists and IS the samefile, or if something went wrong.
                         # We assume we just use the existing one.
                         print(f"Using existing file: '{dest_path}'")

                    # Add the final (potentially renamed) filename to the list if not already there
                    if final_filename not in self.slide_layers:
                        self.slide_layers.append(final_filename)

                except OSError as e: # Catch potential samefile errors on some systems/networks
                     QMessageBox.critical(self, "File Check Error", f"Could not check or copy {source_file_path}:\n{e}")
                except Exception as e:
                    QMessageBox.critical(self, "File Copy Error", f"Could not process {source_file_path}:\n{e}")

            self.populate_layers_list()
    # --- END MODIFIED FUNCTION ---

    def remove_layer(self):
        current_item = self.layers_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Remove Layer", "Please select a layer to remove.")
            return

        row = self.layers_list_widget.row(current_item)
        del self.slide_layers[row]
        self.populate_layers_list()

    def preview_slide_on_display(self):
        if not self.display_window: return
        self.update_internal_layers_from_widget()
        print(f"Previewing slide with layers: {self.slide_layers} from base: {self.media_path}")
        self.display_window.display_images(self.slide_layers, self.media_path)

    def update_internal_layers_from_widget(self):
        """Updates self.slide_layers based on the current order in QListWidget."""
        self.slide_layers = [self.layers_list_widget.item(i).text() for i in range(self.layers_list_widget.count())]

    def accept_changes(self):
        self.update_internal_layers_from_widget()
        self.accept()

    def get_updated_layers(self):
        return self.slide_layers