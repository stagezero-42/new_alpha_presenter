# myapp/gui/playlist_editor.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QMessageBox,
    QListWidgetItem, QAbstractItemView, QFrame # Removed QInputDialog, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

# --- MODIFIED: Import new helpers ---
from .file_dialog_helpers import get_themed_open_filename, get_themed_save_filename
# --- END MODIFIED ---
from .layer_editor_dialog import LayerEditorDialog
from ..playlist.playlist import Playlist
from ..utils.paths import get_playlists_path, get_media_path, get_playlist_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)

class PlaylistEditorWindow(QMainWindow):
    playlist_saved_signal = Signal(str)

    def __init__(self, display_window_instance, playlist_obj, parent=None):
        super().__init__(parent)
        logger.debug(f"Initializing PlaylistEditorWindow. Current playlist has {len(playlist_obj.get_slides())} slides.")
        self.base_title = "Playlist Editor"
        self.display_window = display_window_instance
        self.playlist = playlist_obj
        self.playlists_base_dir = get_playlists_path()

        self.setWindowTitle(f"{self.base_title} [*]")
        self.setGeometry(100, 100, 700, 600)
        self.setWindowModified(False)
        self.setup_ui()
        self.update_title()
        self.populate_list()
        logger.debug("PlaylistEditorWindow initialized.")

    def setup_ui(self):
        logger.debug("Setting up PlaylistEditorWindow UI...")
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        toolbar_layout = QHBoxLayout()
        self.new_button = create_button(" New", "new.png", on_click=self.new_playlist)
        self.load_button = create_button(" Load", "load.png", on_click=self.load_playlist_dialog)
        self.save_button = create_button(" Save", "save.png", on_click=self.save_playlist)
        self.save_as_button = create_button(" Save As...", "save.png", on_click=self.save_playlist_as)
        self.done_button = create_button(" Done", "done.png", on_click=self.close)

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
        self.add_slide_button = create_button(" Add Slide", "add.png", on_click=self.add_slide)
        self.edit_slide_button = create_button(" Edit Slide", "edit.png", on_click=self.edit_selected_slide_layers)
        self.preview_slide_button = create_button(" Preview Slide", "preview.png", on_click=self.preview_selected_slide)
        self.remove_slide_button = create_button(" Remove Slide", "remove.png", on_click=self.remove_slide)

        slide_controls_layout.addWidget(self.add_slide_button)
        slide_controls_layout.addWidget(self.edit_slide_button)
        slide_controls_layout.addWidget(self.preview_slide_button)
        slide_controls_layout.addWidget(self.remove_slide_button)
        main_layout.addLayout(slide_controls_layout)

        self.setCentralWidget(central_widget)
        logger.debug("PlaylistEditorWindow UI setup complete.")

    def mark_dirty(self, dirty=True):
        logger.debug(f"Marking window as dirty: {dirty}")
        self.setWindowModified(dirty)

    def update_title(self):
        title = self.base_title
        if self.playlist and self.playlist.file_path:
            title += f" - {os.path.basename(self.playlist.file_path)}"
        else:
            title += " - Untitled"
        title += " [*]"
        self.setWindowTitle(title)
        logger.debug(f"Window title updated to: {title.replace(' [*]', '')}")

    def populate_list(self):
        logger.debug("Populating playlist list widget.")
        self.playlist_list.clear()
        for i, slide in enumerate(self.playlist.get_slides()):
            layers_str = ", ".join(slide.get("layers", []))
            duration = slide.get("duration", 0)
            loop_target = slide.get("loop_to_slide", 0)

            duration_info = f" ({duration}s"
            if duration > 0 and loop_target > 0:
                duration_info += f", Loop to S{loop_target})"
            elif duration > 0:
                duration_info += ")"
            else:
                duration_info = " (Manual"
                if loop_target > 0:
                    duration_info += f", Loop to S{loop_target} inactive)"
                else:
                    duration_info += ")"

            item_text = f"Slide {i + 1}{duration_info}: {layers_str if layers_str else '[Empty Slide]'}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, slide)
            self.playlist_list.addItem(item)
        logger.info(f"Playlist list populated with {self.playlist_list.count()} items.")

    def update_playlist_from_list_order(self):
        logger.debug("Updating internal playlist order from list widget.")
        new_slides = [self.playlist_list.item(i).data(Qt.ItemDataRole.UserRole)
                      for i in range(self.playlist_list.count())]
        self.playlist.set_slides(new_slides)
        self.mark_dirty()
        logger.debug("Internal playlist order updated.")

    def new_playlist(self):
        logger.info("New playlist action triggered.")
        if self.isWindowModified():
            logger.debug("Window has unsaved changes, prompting user.")
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Cancel:
                logger.info("New playlist action cancelled by user at save prompt.")
                return

        self.playlist = Playlist()
        self.populate_list()
        self.update_title()
        self.mark_dirty(False)
        logger.info("New empty playlist created.")

    def add_slide(self):
        logger.info("Add slide action triggered.")
        self.update_playlist_from_list_order()
        new_slide = {"layers": [], "duration": 0, "loop_to_slide": 0}
        self.playlist.add_slide(new_slide)
        self.populate_list()
        new_slide_index = self.playlist_list.count() - 1
        self.playlist_list.setCurrentRow(new_slide_index)
        self.mark_dirty()
        logger.info(f"New slide added at index {new_slide_index}. Opening editor.")
        self.edit_selected_slide_layers()

    def remove_slide(self):
        logger.debug("Remove slide action triggered.")
        current_item = self.playlist_list.currentItem()
        if not current_item:
            logger.warning("Remove slide called but no item selected.")
            return
        row = self.playlist_list.row(current_item)
        self.playlist_list.takeItem(row)
        self.update_playlist_from_list_order()
        self.populate_list()
        self.mark_dirty()
        logger.info(f"Slide at index {row} removed.")

    def edit_selected_slide_layers(self):
        logger.debug("Edit selected slide action triggered.")
        current_item = self.playlist_list.currentItem()
        if not current_item:
            logger.warning("Edit slide called but no item selected.")
            return
        self.edit_slide_layers_dialog(current_item)

    def edit_slide_layers_dialog(self, item):
        row = self.playlist_list.row(item)
        slide_data = self.playlist.get_slide(row)
        if not slide_data:
            logger.error(f"Could not retrieve slide data for row {row} during edit.")
            return

        logger.info(f"Opening layer editor for slide at index {row}.")
        current_layers = slide_data.get("layers", [])
        current_duration = slide_data.get("duration", 0)
        current_loop_target = slide_data.get("loop_to_slide", 0)

        editor = LayerEditorDialog(current_layers, current_duration, current_loop_target, self.display_window, self)

        if editor.exec():
            logger.info(f"Layer editor for slide {row} accepted.")
            updated_data = editor.get_updated_slide_data()

            changed = (slide_data.get("layers", []) != updated_data["layers"] or \
                       slide_data.get("duration", 0) != updated_data["duration"] or \
                       slide_data.get("loop_to_slide", 0) != updated_data["loop_to_slide"])

            if changed:
                logger.info(f"Slide {row} data changed. Updating playlist.")
                slide_data["layers"] = updated_data["layers"]
                slide_data["duration"] = updated_data["duration"]
                slide_data["loop_to_slide"] = updated_data["loop_to_slide"]
                self.playlist.update_slide(row, slide_data)
                self.mark_dirty()
            else:
                logger.info(f"Layer editor for slide {row} closed with no changes.")

            self.populate_list()
            self.playlist_list.setCurrentRow(row)
        else:
            logger.info(f"Layer editor for slide {row} cancelled.")


    def preview_selected_slide(self):
        logger.debug("Preview selected slide action triggered.")
        current_item = self.playlist_list.currentItem()
        if not current_item:
            logger.warning("Preview slide called but no item selected.")
            return
        if not self.display_window:
            logger.warning("Preview slide called but no display window available.")
            return

        row = self.playlist_list.row(current_item)
        slide_data = self.playlist.get_slide(row)
        if slide_data:
            layers_to_preview = slide_data.get("layers", [])
            logger.info(f"Previewing slide at index {row} with layers: {layers_to_preview}")
            self.display_window.display_images(layers_to_preview)

    def load_playlist_dialog(self):
        logger.info("Load playlist dialog action triggered.")
        if self.isWindowModified():
            logger.debug("Window has unsaved changes, prompting user.")
            if self.prompt_save_changes() == QMessageBox.StandardButton.Cancel:
                logger.info("Load playlist action cancelled by user at save prompt.")
                return

        # --- MODIFIED: Use new helper ---
        file_name = get_themed_open_filename(self, "Load Playlist", self.playlists_base_dir,
                                             "JSON Files (*.json)")
        # --- END MODIFIED ---

        if file_name:
            logger.info(f"User selected playlist file to load: {file_name}")
            try:
                self.playlist.load(file_name)
                self.populate_list()
                self.update_title()
                self.mark_dirty(False)
                self.playlist_saved_signal.emit(file_name)
                logger.info(f"Successfully loaded playlist: {file_name}")
            except (FileNotFoundError, ValueError) as e:
                logger.error(f"Failed to load playlist '{file_name}': {e}", exc_info=True)
                QMessageBox.critical(self, "Load Error", f"Failed to load playlist: {e}")
        else:
            logger.info("Load playlist dialog cancelled by user.")


    def save_playlist(self):
        logger.info("Save playlist action triggered.")
        self.update_playlist_from_list_order()
        if not self.playlist.file_path:
            logger.info("Playlist has no current file path, calling Save As...")
            return self.save_playlist_as()
        else:
            logger.info(f"Saving playlist to: {self.playlist.file_path}")
            if self.playlist.save(self.playlist.file_path):
                self.mark_dirty(False)
                QMessageBox.information(self, "Save Success", "Playlist saved.")
                self.playlist_saved_signal.emit(self.playlist.file_path)
                logger.info("Playlist saved successfully.")
                return True
            else:
                logger.error(f"Failed to save playlist to {self.playlist.file_path}")
                QMessageBox.critical(self, "Save Error", "Failed to save playlist.")
                return False

    def save_playlist_as(self):
        logger.info("Save playlist as action triggered.")
        self.update_playlist_from_list_order()

        # --- MODIFIED: Use QFileDialog via helper ---
        full_save_path = get_themed_save_filename(self, "Save Playlist As",
                                                   self.playlists_base_dir,
                                                   "JSON Files (*.json)")

        if full_save_path:
            filename = os.path.basename(full_save_path)
            logger.debug(f"User selected filename for Save As: {filename} ({full_save_path})")

            # Ensure .json extension if QFileDialog didn't add it
            if not filename.lower().endswith('.json'):
                full_save_path += '.json'
                filename += '.json'
                logger.debug(f"Appended .json extension, path is now: {full_save_path}")

            # Security check on the final basename
            if not is_safe_filename_component(filename):
                logger.error(f"Save As failed: unsafe filename '{filename}' provided.")
                QMessageBox.critical(self, "Save Error",
                                     f"The filename '{filename}' is invalid or "
                                     f"contains forbidden characters/patterns.")
                return False

            # Check if it should be in the playlists directory
            if os.path.dirname(full_save_path) != self.playlists_base_dir:
                 logger.warning(f"File saved outside default playlists dir: {full_save_path}")
                 reply = QMessageBox.question(self, "Confirm Save Location",
                                              f"Save outside the default 'playlists' folder?\n({full_save_path})",
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                 if reply == QMessageBox.StandardButton.No:
                     logger.info("User chose not to save outside default dir. Save As cancelled.")
                     return False


            # Check for overwrite (QFileDialog non-native might not prompt)
            if os.path.exists(full_save_path):
                logger.warning(f"File '{full_save_path}' already exists, prompting for overwrite.")
                reply = QMessageBox.question(self, "Confirm Overwrite", f"'{filename}' exists. Overwrite?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    logger.info("User chose not to overwrite. Save As cancelled.")
                    return False

            if self.playlist.save(full_save_path):
                self.update_title()
                self.mark_dirty(False)
                QMessageBox.information(self, "Save Success", f"Playlist saved as {filename}.")
                self.playlist_saved_signal.emit(full_save_path)
                logger.info(f"Playlist successfully saved as {full_save_path}")
                return True
            else:
                logger.error(f"Failed to save playlist to {full_save_path}")
                QMessageBox.critical(self, "Save Error", "Failed to save playlist.")
                return False
        else:
            logger.info("Save As dialog cancelled or no filename entered.")
            return False
        # --- END MODIFIED ---

    def prompt_save_changes(self):
        logger.debug("Prompting user to save unsaved changes.")
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "Save changes before proceeding?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)
        if reply == QMessageBox.StandardButton.Save:
            logger.info("User chose to Save changes.")
            return QMessageBox.StandardButton.Save if self.save_playlist() else QMessageBox.StandardButton.Cancel
        elif reply == QMessageBox.StandardButton.Discard:
            logger.info("User chose to Discard changes.")
        else: # Cancel
            logger.info("User chose to Cancel operation.")
        return reply

    def closeEvent(self, event):
        logger.debug("PlaylistEditorWindow closeEvent triggered.")
        if self.isWindowModified():
            logger.info("Window has unsaved changes, prompting user before closing.")
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Cancel:
                logger.info("Close event ignored due to user cancelling save prompt.")
                event.ignore()
                return
        event.accept()
        if event.isAccepted():
            logger.info("PlaylistEditorWindow closing.")
            if self.display_window:
                logger.debug("Clearing display window on PlaylistEditor close.")
                self.display_window.clear_display()