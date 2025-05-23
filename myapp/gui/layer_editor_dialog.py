# myapp/gui/layer_editor_dialog.py
import os
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QFileDialog, QMessageBox, QAbstractItemView, QListWidgetItem
)
from PySide6.QtCore import Qt


class LayerEditorDialog(QDialog):
    def __init__(self, slide_layers, media_dir, display_window_instance, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Slide Layers")
        self.slide_layers = list(slide_layers)  # Work on a copy
        self.media_dir = media_dir  # Base directory for media (e.g., .../playlist_name_media_files/)
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
        self.add_layer_button = QPushButton("Add Image(s)")
        self.remove_layer_button = QPushButton("Remove Selected")
        self.preview_button = QPushButton("Preview Slide")

        self.add_layer_button.clicked.connect(self.add_layers)
        self.remove_layer_button.clicked.connect(self.remove_layer)
        self.preview_button.clicked.connect(self.preview_slide_on_display)

        buttons_layout.addWidget(self.add_layer_button)
        buttons_layout.addWidget(self.remove_layer_button)
        buttons_layout.addWidget(self.preview_button)
        main_layout.addLayout(buttons_layout)

        # Ok and Cancel buttons
        ok_cancel_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")

        self.ok_button.clicked.connect(self.accept_changes)
        self.cancel_button.clicked.connect(self.reject)

        ok_cancel_layout.addStretch()
        ok_cancel_layout.addWidget(self.ok_button)
        ok_cancel_layout.addWidget(self.cancel_button)
        main_layout.addLayout(ok_cancel_layout)

    def populate_layers_list(self):
        self.layers_list_widget.clear()
        for layer_path in self.slide_layers:
            self.layers_list_widget.addItem(QListWidgetItem(layer_path))

    def add_layers(self):
        if not self.media_dir or not os.path.isdir(self.media_dir):
            QMessageBox.warning(self, "Media Directory Not Set",
                                "The media directory for this playlist is not set or valid. Please save the playlist first.")
            return

        file_names, _ = QFileDialog.getOpenFileNames(
            self, "Select Image Files to Add as Layers", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
        )

        if file_names:
            for file_path in file_names:
                try:
                    dest_file_name = os.path.basename(file_path)
                    dest_path = os.path.join(self.media_dir, dest_file_name)

                    if not os.path.exists(dest_path) or not os.path.samefile(file_path, dest_path):
                        shutil.copy2(file_path, dest_path)
                        print(f"Copied {file_path} to {dest_path}")

                    self.slide_layers.append(dest_file_name)  # Add relative path
                except Exception as e:
                    QMessageBox.critical(self, "File Copy Error", f"Could not copy {file_path}:\n{e}")
                    # Continue with other files if one fails? Or stop? For now, continue.
            self.populate_layers_list()

    def remove_layer(self):
        current_item = self.layers_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Remove Layer", "Please select a layer to remove.")
            return

        row = self.layers_list_widget.row(current_item)
        del self.slide_layers[row]
        self.populate_layers_list()

    def preview_slide_on_display(self):
        if not self.display_window:
            QMessageBox.warning(self, "Preview Error", "Display window reference is not available.")
            return

        if not self.media_dir:
            QMessageBox.warning(self, "Preview Error", "Media directory is not set. Cannot resolve layer paths.")
            return

        # Update layers from the current list order before previewing
        self.update_internal_layers_from_widget()

        print(f"Previewing slide with layers: {self.slide_layers} from base: {self.media_dir}")
        self.display_window.display_images(self.slide_layers, self.media_dir)

    def update_internal_layers_from_widget(self):
        """Updates self.slide_layers based on the current order in QListWidget."""
        self.slide_layers = [self.layers_list_widget.item(i).text() for i in range(self.layers_list_widget.count())]

    def accept_changes(self):
        self.update_internal_layers_from_widget()
        self.accept()  # QDialog.accept()

    def get_updated_layers(self):
        return self.slide_layers
