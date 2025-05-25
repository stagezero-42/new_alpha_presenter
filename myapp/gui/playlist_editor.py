# myapp/gui/playlist_editor.py
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QFileDialog, QMessageBox,
    QListWidgetItem, QAbstractItemView, QInputDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from .layer_editor_dialog import LayerEditorDialog
from ..playlist.playlist import Playlist
from ..utils.paths import get_playlists_path, get_icon_file_path, get_media_path

class PlaylistEditorWindow(QMainWindow):
    playlist_saved_signal = Signal(str)

    def __init__(self, display_window_instance, playlist_obj, parent=None):
        super().__init__(parent)
        self.base_title = "Playlist Editor"
        self.display_window = display_window_instance
        self.playlist = playlist_obj # Use the passed Playlist object
        self.playlists_base_dir = get_playlists_path() # Get central playlists path

        self.setWindowTitle(f"{self.base_title} [*]")
        self.setGeometry(100, 100, 700, 600)
        self.setWindowModified(False)
        self.setup_ui()
        self.update_title()
        self.populate_list()

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        toolbar_layout = QHBoxLayout()
        self.new_button = QPushButton(" New")
        self.load_button = QPushButton(" Load")
        self.save_button = QPushButton(" Save")
        self.save_as_button = QPushButton(" Save As...")
        self.done_button = QPushButton(" Done")

        self.new_button.setIcon(QIcon(get_icon_file_path("new.png")))
        self.load_button.setIcon(QIcon(get_icon_file_path("load.png")))
        self.save_button.setIcon(QIcon(get_icon_file_path("save.png")))
        self.save_as_button.setIcon(QIcon(get_icon_file_path("save.png"))) # Can use same
        self.done_button.setIcon(QIcon(get_icon_file_path("close.png")))

        self.new_button.clicked.connect(self.new_playlist)
        self.load_button.clicked.connect(self.load_playlist_dialog)
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
        self.add_slide_button = QPushButton(" Add Slide")
        self.edit_layers_button = QPushButton(" Edit Slide")
        self.preview_slide_button = QPushButton(" Preview Slide")
        self.remove_slide_button = QPushButton(" Remove Slide")

        self.add_slide_button.setIcon(QIcon(get_icon_file_path("add.png")))
        self.edit_layers_button.setIcon(QIcon(get_icon_file_path("edit.png")))
        self.preview_slide_button.setIcon(QIcon(get_icon_file_path("preview.png")))
        self.remove_slide_button.setIcon(QIcon(get_icon_file_path("remove.png")))

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

    def update_title(self):
        title = self.base_title
        if self.playlist and self.playlist.file_path:
            title += f" - {os.path.basename(self.playlist.file_path)}"
        else:
            title += " - Untitled"
        title += " [*]" # Shows modification status
        self.setWindowTitle(title)

    def populate_list(self):
        self.playlist_list.clear()
        for i, slide in enumerate(self.playlist.get_slides()):
            layers_str = ", ".join(slide.get("layers", []))
            item_text = f"Slide {i + 1}: {layers_str if layers_str else '[Empty Slide]'}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, slide) # Store data with item
            self.playlist_list.addItem(item)

    def update_playlist_from_list_order(self):
        """Syncs the internal playlist order with the QListWidget order."""
        new_slides = [self.playlist_list.item(i).data(Qt.ItemDataRole.UserRole)
                      for i in range(self.playlist_list.count())]
        self.playlist.set_slides(new_slides)
        self.mark_dirty()

    def new_playlist(self):
        if self.isWindowModified():
            if self.prompt_save_changes() == QMessageBox.StandardButton.Cancel: return
        self.playlist = Playlist()
        self.populate_list()
        self.update_title()
        self.mark_dirty(False)

    def add_slide(self):
        self.update_playlist_from_list_order()
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
        self.playlist_list.takeItem(row) # Remove from list
        self.update_playlist_from_list_order() # Re-sync internal data
        self.populate_list() # Repopulate to fix numbering

    def edit_selected_slide_layers(self):
        current_item = self.playlist_list.currentItem()
        if not current_item: return
        self.edit_slide_layers_dialog(current_item)

    def edit_slide_layers_dialog(self, item):
        row = self.playlist_list.row(item)
        slide_data = self.playlist.get_slide(row)
        if not slide_data: return # Should not happen

        editor = LayerEditorDialog(slide_data.get("layers", []), self.display_window, self)
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
        if not current_item or not self.display_window: return
        row = self.playlist_list.row(current_item)
        slide_data = self.playlist.get_slide(row)
        if slide_data:
            self.display_window.display_images(slide_data.get("layers", []), get_media_path())

    def load_playlist_dialog(self):
        if self.isWindowModified():
            if self.prompt_save_changes() == QMessageBox.StandardButton.Cancel: return

        file_name, _ = QFileDialog.getOpenFileName(self, "Load Playlist", self.playlists_base_dir,
                                                   "JSON Files (*.json)")
        if file_name:
            try:
                self.playlist.load(file_name)
                self.populate_list()
                self.update_title()
                self.mark_dirty(False)
                self.playlist_saved_signal.emit(file_name) # Notify ControlWindow
            except (FileNotFoundError, ValueError) as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load playlist: {e}")

    def save_playlist(self):
        self.update_playlist_from_list_order()
        if not self.playlist.file_path:
            return self.save_playlist_as()
        else:
            if self.playlist.save(self.playlist.file_path):
                self.mark_dirty(False)
                QMessageBox.information(self, "Save Success", "Playlist saved.")
                self.playlist_saved_signal.emit(self.playlist.file_path)
                return True
            else:
                QMessageBox.critical(self, "Save Error", "Failed to save playlist.")
                return False

    def save_playlist_as(self):
        self.update_playlist_from_list_order()
        current_filename = os.path.basename(self.playlist.file_path) if self.playlist.file_path else "untitled.json"
        filename, ok = QInputDialog.getText(self, "Save Playlist As", "Enter filename:", text=current_filename)

        if ok and filename:
            if not filename.lower().endswith('.json'):
                filename += '.json'
            full_save_path = os.path.join(self.playlists_base_dir, filename)

            if os.path.exists(full_save_path):
                reply = QMessageBox.question(self, "Confirm Overwrite", f"'{filename}' exists. Overwrite?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: return False

            if self.playlist.save(full_save_path):
                self.update_title()
                self.mark_dirty(False)
                QMessageBox.information(self, "Save Success", f"Playlist saved as {filename}.")
                self.playlist_saved_signal.emit(full_save_path)
                return True
            else:
                QMessageBox.critical(self, "Save Error", "Failed to save playlist.")
                return False
        return False

    def prompt_save_changes(self):
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "Save changes before proceeding?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)
        if reply == QMessageBox.StandardButton.Save:
            return QMessageBox.StandardButton.Save if self.save_playlist() else QMessageBox.StandardButton.Cancel
        return reply

    def closeEvent(self, event):
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()
        if event.isAccepted() and self.display_window:
            self.display_window.clear_display()