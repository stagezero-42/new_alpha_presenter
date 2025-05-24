# myapp/gui/playlist_editor.py
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QFileDialog, QMessageBox,
    QListWidgetItem, QAbstractItemView, QInputDialog
)
from PySide6.QtCore import Qt, Signal

from .layer_editor_dialog import LayerEditorDialog
from ..playlist.playlist import Playlist

class PlaylistEditorWindow(QMainWindow):
    playlist_saved_signal = Signal(str)

    def __init__(self, display_window_instance, playlist, parent=None):
        super().__init__(parent)
        self.base_title = "Playlist Editor"
        self.setWindowTitle(f"{self.base_title} [*]")
        self.setGeometry(100, 100, 700, 600)

        self.display_window = display_window_instance
        self.playlist = playlist

        self.setWindowModified(False)
        self.setup_ui()
        self.populate_list()

        if not self.playlist.file_path:
            self.setWindowTitle(f"{self.base_title} - Untitled [*]")
            self.mark_dirty(False)
        else:
            self.setWindowTitle(f"{self.base_title} - {os.path.basename(self.playlist.file_path)} [*]")

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        toolbar_layout = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.load_button = QPushButton("Load")
        self.save_button = QPushButton("Save")
        self.save_as_button = QPushButton("Save As...")
        self.done_button = QPushButton("Done")

        self.new_button.clicked.connect(self.new_playlist)
        self.load_button.clicked.connect(self.load_playlist)
        self.save_button.clicked.connect(self.save_playlist)
        self.save_as_button.clicked.connect(self.save_playlist_as)
        self.done_button.clicked.connect(self.close)

        toolbar_layout.addWidget(self.new_button)
        toolbar_layout.addWidget(self.load_button)
        toolbar_layout.addWidget(self.save_button)
        toolbar_layout.addWidget(self.save_as_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.done_button)
        main_layout.addLayout(toolbar_layout)

        self.playlist_list = QListWidget()
        self.playlist_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.playlist_list.itemDoubleClicked.connect(self.edit_slide_layers_dialog)
        main_layout.addWidget(self.playlist_list)

        slide_controls_layout = QHBoxLayout()
        self.add_slide_button = QPushButton("Add Slide")
        self.edit_layers_button = QPushButton("Edit Selected Slide Layers")
        self.preview_slide_button = QPushButton("Preview Selected Slide")
        self.remove_slide_button = QPushButton("Remove Selected Slide")

        self.add_slide_button.clicked.connect(self.add_slide)
        self.edit_layers_button.clicked.connect(self.edit_selected_slide_layers)
        self.preview_slide_button.clicked.connect(self.preview_selected_slide)
        self.remove_slide_button.clicked.connect(self.remove_slide)

        slide_controls_layout.addWidget(self.add_slide_button)
        slide_controls_layout.addWidget(self.edit_layers_button)
        slide_controls_layout.addWidget(self.preview_slide_button)
        slide_controls_layout.addWidget(self.remove_slide_button)
        main_layout.addLayout(slide_controls_layout)

        self.setCentralWidget(central_widget)

    def mark_dirty(self, dirty=True):
        self.setWindowModified(dirty)

    def populate_list(self):
        self.playlist_list.clear()
        for i, slide in enumerate(self.playlist.get_slides()):
            layers_str = ", ".join(slide.get("layers", []))
            item_text = f"Slide {i + 1}: {layers_str if layers_str else '[Empty Slide]'}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, slide)
            self.playlist_list.addItem(item)

    def new_playlist(self):
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_playlist(): return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.playlist = Playlist()
        self.populate_list()
        self.setWindowTitle(f"{self.base_title} - Untitled [*]")
        self.mark_dirty(False)

    def add_slide(self):
        new_slide = {"layers": []}
        self.playlist.add_slide(new_slide)
        self.populate_list()
        self.playlist_list.setCurrentRow(self.playlist_list.count() - 1)
        self.mark_dirty()
        self.edit_selected_slide_layers()

    def remove_slide(self):
        current_item = self.playlist_list.currentItem()
        if not current_item: return
        row = self.playlist_list.row(current_item)
        self.playlist.remove_slide(row)
        self.populate_list()
        self.mark_dirty()

    def edit_selected_slide_layers(self):
        current_item = self.playlist_list.currentItem()
        if not current_item: return
        self.edit_slide_layers_dialog(current_item)

    def edit_slide_layers_dialog(self, item):
        row = self.playlist_list.row(item)
        slide_data = self.playlist.get_slide(row)
        current_layers = slide_data.get("layers", [])

        if not self.playlist.get_media_dir():
            QMessageBox.warning(self, "Set Playlist Location",
                                "Please save this new playlist first (using 'Save As...') to establish its media location.")
            if not self.save_playlist_as():
                return

        editor = LayerEditorDialog(current_layers, self.playlist.get_media_dir(), self.display_window, self)
        if editor.exec():
            updated_layers = editor.get_updated_layers()
            if slide_data.get("layers", []) != updated_layers:
                slide_data["layers"] = updated_layers
                self.playlist.update_slide(row, slide_data)
                self.mark_dirty()
            self.populate_list()
            self.playlist_list.setCurrentRow(row)

    def preview_selected_slide(self):
        current_item = self.playlist_list.currentItem()
        if not current_item: return
        if not self.display_window: return

        if not self.playlist.get_media_dir():
            QMessageBox.warning(self, "Preview Error",
                                "Media directory is not established. Please save the playlist first or ensure it's loaded correctly.")
            return

        row = self.playlist_list.row(current_item)
        slide_data = self.playlist.get_slide(row)
        layers_to_preview = slide_data.get("layers", [])
        self.display_window.display_images(layers_to_preview, self.playlist.get_media_dir())

    def load_playlist(self):
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_playlist(): return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        file_name, _ = QFileDialog.getOpenFileName(self, "Load Playlist", self.playlist.get_user_playlists_base_dir(),
                                                   "JSON Files (*.json)")
        if file_name:
            try:
                self.playlist.load(file_name)
                self.populate_list()
                self.setWindowTitle(f"{self.base_title} - {os.path.basename(self.playlist.file_path)} [*]")
                self.mark_dirty(False)
            except (FileNotFoundError, ValueError) as e:
                QMessageBox.critical(self, "Load Error", str(e))

    def save_playlist(self):
        if not self.playlist.file_path:
            return self.save_playlist_as()
        else:
            try:
                self.playlist.save()
                self.mark_dirty(False)
                QMessageBox.information(self, "Save Success", f"Playlist saved to {self.playlist.file_path}")
                self.playlist_saved_signal.emit(self.playlist.file_path)
                return True
            except ValueError as e:
                QMessageBox.critical(self, "Save Error", str(e))
                return False

    def save_playlist_as(self):
        current_filename_suggestion = os.path.basename(
            self.playlist.file_path) if self.playlist.file_path else "untitled.json"

        filename, ok = QInputDialog.getText(self, "Save Playlist As",
                                            "Enter filename for new playlist (in user_created_playlists):",
                                            text=current_filename_suggestion)
        if ok and filename:
            if not filename.lower().endswith('.json'):
                filename += '.json'
            full_save_path = os.path.join(self.playlist.get_user_playlists_base_dir(), filename)

            if os.path.exists(full_save_path) and \
                    (not self.playlist.file_path or os.path.normpath(full_save_path) != os.path.normpath(
                        self.playlist.file_path)):
                reply = QMessageBox.question(self, "Confirm Save As",
                                             f"'{filename}' already exists. Overwrite?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return False

            try:
                self.playlist.save(full_save_path)
                self.setWindowTitle(f"{self.base_title} - {os.path.basename(self.playlist.file_path)} [*]")
                self.mark_dirty(False)
                QMessageBox.information(self, "Save Success", f"Playlist saved to {self.playlist.file_path}")
                self.playlist_saved_signal.emit(self.playlist.file_path)
                return True
            except ValueError as e:
                QMessageBox.critical(self, "Save Error", str(e))
                return False
        return False

    def prompt_save_changes(self):
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "You have unsaved changes. Do you want to save them before proceeding?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)
        return reply

    def closeEvent(self, event):
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_playlist():
                    event.ignore();
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore();
                return

        event.accept()
        if event.isAccepted():
            if self.display_window:
                self.display_window.clear_display()