# myapp/gui/playlist_editor.py
import os
import logging
import copy
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QListWidget, QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from .file_dialog_helpers import get_themed_open_filename, get_themed_save_filename
from .layer_editor_dialog import LayerEditorDialog
from .video_editor_dialog import VideoEditorDialog
from .settings_window import SettingsWindow
from .text_editor_window import TextEditorWindow
from .audio_program_editor_window import AudioProgramEditorWindow

from ..playlist.playlist import Playlist, get_default_slide_audio_settings
from ..utils.paths import get_playlists_path, get_icon_file_path, get_media_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)


class PlaylistEditorWindow(QMainWindow):
    playlist_saved_signal = Signal(str)

    def __init__(self, display_window_instance, playlist_obj, parent=None):
        super().__init__(parent)
        logger.debug(
            f"Initializing PlaylistEditorWindow. Current playlist has {len(playlist_obj.get_slides())} slides.")
        self.base_title = "Playlist Editor"
        self.display_window = display_window_instance
        self.playlist = playlist_obj
        self.playlists_base_dir = get_playlists_path()

        self.setWindowTitle(f"{self.base_title} [*]")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowModified(False)
        self.settings_window_instance = None
        self.text_editor_window_instance = None
        self.audio_program_editor_instance = None

        try:
            icon_name = "edit.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set PlaylistEditor window icon: {e}", exc_info=True)

        self.setup_ui()
        self.update_title()
        self.populate_list()
        self.update_button_states()
        logger.debug("PlaylistEditorWindow initialized.")

    def setup_ui(self):
        logger.debug("Setting up PlaylistEditorWindow UI...")
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        toolbar_layout = QHBoxLayout()
        self.new_button = create_button(" New", "new.png", "Create a new playlist", self.new_playlist)
        self.load_button = create_button(" Load", "load.png", "Load an existing playlist", self.load_playlist_dialog)
        self.save_button = create_button(" Save", "save.png", "Save the current playlist", self.save_playlist)
        self.save_as_button = create_button(" Save As...", "save.png", "Save the current playlist under a new name",
                                            self.save_playlist_as)
        self.settings_button = create_button(" Settings", "settings.png", "Application settings",
                                             self.open_settings_window)
        self.done_button = create_button(" Done", "done.png", "Close the playlist editor", self.close)

        toolbar_layout.addWidget(self.new_button)
        toolbar_layout.addWidget(self.load_button)
        toolbar_layout.addWidget(self.save_button)
        toolbar_layout.addWidget(self.save_as_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.settings_button)
        toolbar_layout.addWidget(self.done_button)
        main_layout.addLayout(toolbar_layout)

        self.playlist_list = QListWidget()
        self.playlist_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.playlist_list.itemDoubleClicked.connect(self.edit_slide_layers_dialog)
        self.playlist_list.currentItemChanged.connect(self.update_button_states)  # Update buttons on selection change
        main_layout.addWidget(self.playlist_list)

        slide_controls_layout = QHBoxLayout()
        self.add_slide_button = create_button(" Add Image Slide", "add.png", "Add a new image-based slide",
                                              self.add_slide)
        # --- FIX: Connect to the new context-aware method ---
        self.add_video_button = create_button(" Add Video Slide", "video.png", "Add or edit a video slide",
                                              self.add_or_edit_video_slide)
        # --- END FIX ---
        self.duplicate_slide_button = create_button(" Duplicate Slide", "duplicate.png", "Duplicate selected slide",
                                                    self.duplicate_selected_slide)
        self.edit_slide_button = create_button(" Edit Slide Details", "edit.png", "Edit selected slide (images only)",
                                               self.edit_selected_slide_layers)
        self.edit_text_button = create_button(" Edit Text Paragraphs", "text.png", "Open Text Editor",
                                              self.open_text_editor)
        self.edit_audio_programs_button = create_button(" Edit Audio Programs", "audio_icon.png",
                                                        "Open Audio Program Editor", self.open_audio_program_editor)
        self.preview_slide_button = create_button(" Preview Slide", "preview.png", "Preview selected slide",
                                                  self.preview_selected_slide)
        self.remove_slide_button = create_button(" Remove Slide", "remove.png", "Remove selected slide",
                                                 self.remove_slide)

        slide_controls_layout.addWidget(self.add_slide_button)
        slide_controls_layout.addWidget(self.add_video_button)
        slide_controls_layout.addWidget(self.duplicate_slide_button)
        slide_controls_layout.addWidget(self.edit_slide_button)
        slide_controls_layout.addWidget(self.edit_text_button)
        slide_controls_layout.addWidget(self.edit_audio_programs_button)
        slide_controls_layout.addWidget(self.preview_slide_button)
        slide_controls_layout.addWidget(self.remove_slide_button)
        main_layout.addLayout(slide_controls_layout)

        self.setCentralWidget(central_widget)
        logger.debug("PlaylistEditorWindow UI setup complete.")

    def edit_slide_layers_dialog(self, item):
        row = self.playlist_list.row(item)
        slide_data = self.playlist.get_slide(row)
        if not slide_data:
            logger.error(f"Could not retrieve slide data for row {row} during edit.")
            return

        if slide_data.get("video_path"):
            QMessageBox.information(self, "Edit Slide",
                                    "Video slide properties can be edited using the 'Edit Video Slide' button.")
            return

        logger.info(f"Opening layer/details editor for slide at index {row}.")
        editor = LayerEditorDialog(
            slide_layers=slide_data.get("layers", []),
            current_duration=slide_data.get("duration", 0),
            current_loop_target=slide_data.get("loop_to_slide", 0),
            current_text_overlay=slide_data.get("text_overlay"),
            current_audio_program_name=slide_data.get("audio_program_name"),
            current_loop_audio_program=slide_data.get("loop_audio_program", False),
            current_audio_intro_delay_ms=slide_data.get("audio_intro_delay_ms", 0),
            current_audio_outro_duration_ms=slide_data.get("audio_outro_duration_ms", 0),
            current_audio_program_volume=slide_data.get("audio_program_volume",
                                                        get_default_slide_audio_settings()["audio_program_volume"]),
            display_window_instance=self.display_window,
            parent=self
        )

        if editor.exec():
            logger.info(f"Layer/details editor for slide {row} accepted.")
            updated_data_from_dialog = editor.get_updated_slide_data()
            self.playlist.update_slide(row, updated_data_from_dialog)
            self.mark_dirty()
            self.populate_list()
            self.playlist_list.setCurrentRow(row)
        else:
            logger.info(f"Layer/details editor for slide {row} cancelled.")

    def update_button_states(self):
        current_item = self.playlist_list.currentItem()
        is_item_selected = current_item is not None
        is_video_slide = False
        if is_item_selected:
            slide_data = current_item.data(Qt.ItemDataRole.UserRole)
            is_video_slide = bool(slide_data and slide_data.get("video_path"))

        self.duplicate_slide_button.setEnabled(is_item_selected)
        self.remove_slide_button.setEnabled(is_item_selected)
        self.preview_slide_button.setEnabled(is_item_selected)
        self.edit_slide_button.setEnabled(is_item_selected and not is_video_slide)

        if is_video_slide:
            self.add_video_button.setText(" Edit Video Slide")
            self.add_video_button.setToolTip("Edit the selected video slide")
        else:
            self.add_video_button.setText(" Add Video Slide")
            self.add_video_button.setToolTip("Add a new video-based slide")

    def add_or_edit_video_slide(self):
        current_item = self.playlist_list.currentItem()

        if current_item:
            slide_data = current_item.data(Qt.ItemDataRole.UserRole)
            if slide_data and slide_data.get("video_path"):
                self._edit_selected_video_slide()
                return

        self._add_new_video_slide()

    def _add_new_video_slide(self):
        logger.info("Add new video slide action triggered.")
        video_dialog = VideoEditorDialog(self)
        video_dialog.video_slide_data_updated.connect(self._handle_new_video_slide_creation)
        video_dialog.exec()

    def _edit_selected_video_slide(self):
        logger.info("Edit selected video slide action triggered.")
        current_item = self.playlist_list.currentItem()
        if not current_item: return

        row = self.playlist_list.row(current_item)
        slide_data = self.playlist.get_slide(row)
        if not slide_data or not slide_data.get("video_path"): return

        video_path = get_media_file_path(slide_data.get("video_path"))
        thumb_path = get_media_file_path(slide_data.get("thumbnail_path"))

        video_dialog = VideoEditorDialog(
            self,
            initial_video_path=video_path,
            initial_thumbnail_path=thumb_path
        )
        # Re-use the creation slot, but it will update the slide at the specific row
        video_dialog.video_slide_data_updated.connect(
            lambda new_data: self._handle_edited_video_slide_update(row, new_data)
        )
        video_dialog.exec()

    def _handle_new_video_slide_creation(self, slide_data):
        self.playlist.add_slide(slide_data)
        self.populate_list()
        self.playlist_list.setCurrentRow(self.playlist_list.count() - 1)
        self.mark_dirty()

    def _handle_edited_video_slide_update(self, row, new_slide_data):
        self.playlist.update_slide(row, new_slide_data)
        self.populate_list()
        self.playlist_list.setCurrentRow(row)
        self.mark_dirty()

    # The rest of the methods (open_text_editor, save, load, etc.) remain unchanged...
    def open_text_editor(self):
        logger.info("Opening text editor window...")
        if self.text_editor_window_instance is None or not self.text_editor_window_instance.isVisible():
            self.text_editor_window_instance = TextEditorWindow(self)
            self.text_editor_window_instance.show()
        else:
            self.text_editor_window_instance.activateWindow()
            self.text_editor_window_instance.raise_()

    def open_audio_program_editor(self):
        logger.info("Opening Audio Program Editor window...")
        if self.audio_program_editor_instance is None or not self.audio_program_editor_instance.isVisible():
            self.audio_program_editor_instance = AudioProgramEditorWindow(self)
            self.audio_program_editor_instance.show()
        else:
            self.audio_program_editor_instance.activateWindow()
            self.audio_program_editor_instance.raise_()

    def open_settings_window(self):
        logger.info("Opening settings window...")
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            self.settings_window_instance = SettingsWindow(self)
            self.settings_window_instance.show()
        else:
            self.settings_window_instance.activateWindow()
            self.settings_window_instance.raise_()

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
        current_row = self.playlist_list.currentRow()
        self.playlist_list.clear()

        for i, slide in enumerate(self.playlist.get_slides()):
            video_path = slide.get("video_path")
            if video_path:
                item_text = f"Slide {i + 1} (Video): {os.path.basename(video_path)}"
            else:
                layers_str = ", ".join(slide.get("layers", []))
                item_text = f"Slide {i + 1}: {layers_str if layers_str else '[Empty Image Slide]'}"

            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, slide)
            self.playlist_list.addItem(list_item)

        if 0 <= current_row < self.playlist_list.count():
            self.playlist_list.setCurrentRow(current_row)
        elif self.playlist_list.count() > 0:
            self.playlist_list.setCurrentRow(0)

        self.update_button_states()
        logger.info(f"Playlist list populated with {self.playlist_list.count()} items.")

    def update_playlist_from_list_order(self):
        logger.debug("Updating internal playlist order from list widget.")
        new_slides = []
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item:
                new_slides.append(item.data(Qt.ItemDataRole.UserRole))
        self.playlist.set_slides(new_slides)
        self.mark_dirty()

    def new_playlist(self):
        logger.info("New playlist action triggered.")
        if self.isWindowModified():
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
        default_audio = get_default_slide_audio_settings()
        new_slide_data = {
            "layers": [], "duration": 0, "loop_to_slide": 0, "text_overlay": None,
            "video_path": None, "thumbnail_path": None,
            "audio_program_name": default_audio["audio_program_name"],
            "loop_audio_program": default_audio["loop_audio_program"],
            "audio_intro_delay_ms": default_audio["audio_intro_delay_ms"],
            "audio_outro_duration_ms": default_audio["audio_outro_duration_ms"],
            "audio_program_volume": default_audio["audio_program_volume"]
        }
        self.playlist.add_slide(new_slide_data)
        self.populate_list()
        new_slide_index = self.playlist_list.count() - 1
        self.playlist_list.setCurrentRow(new_slide_index)
        self.mark_dirty()
        logger.info(f"New slide added at index {new_slide_index}. Opening editor.")
        self.edit_selected_slide_layers()

    def duplicate_selected_slide(self):
        logger.info("Duplicate slide action triggered.")
        current_item = self.playlist_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "Duplicate Slide", "Please select a slide to duplicate.")
            return

        row = self.playlist_list.row(current_item)
        original_slide_data = self.playlist.get_slide(row)
        if not original_slide_data:
            logger.error(f"Could not get data for slide at row {row} to duplicate.")
            return

        duplicated_slide_data = copy.deepcopy(original_slide_data)
        self.update_playlist_from_list_order()
        insert_index = row + 1
        self.playlist.insert_slide(insert_index, duplicated_slide_data)
        self.populate_list()
        self.playlist_list.setCurrentRow(insert_index)
        self.mark_dirty()
        logger.info(f"Slide at index {row} duplicated to index {insert_index}.")

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
        if self.playlist_list.count() > 0:
            new_selection_row = min(row, self.playlist_list.count() - 1)
            self.playlist_list.setCurrentRow(new_selection_row)

    def edit_selected_slide_layers(self):
        logger.debug("Edit selected slide action triggered.")
        current_item = self.playlist_list.currentItem()
        if not current_item:
            logger.warning("Edit slide called but no item selected.")
            QMessageBox.information(self, "Edit Slide", "Please select a slide to edit.")
            return
        self.edit_slide_layers_dialog(current_item)

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
            self.display_window.display_slide(slide_data)

    def load_playlist_dialog(self):
        logger.info("Load playlist dialog action triggered.")
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Cancel:
                logger.info("Load playlist action cancelled by user at save prompt.")
                return

        file_name = get_themed_open_filename(self, "Load Playlist", self.playlists_base_dir, "JSON Files (*.json)")
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

        full_save_path = get_themed_save_filename(self, "Save Playlist As", self.playlists_base_dir,
                                                  "JSON Files (*.json)")
        if full_save_path:
            filename = os.path.basename(full_save_path)
            logger.debug(f"User selected filename for Save As: {filename} ({full_save_path})")

            if not filename.lower().endswith('.json'):
                full_save_path += '.json'
                filename += '.json'
                logger.debug(f"Appended .json extension, path is now: {full_save_path}")

            if not is_safe_filename_component(filename):
                logger.error(f"Save As failed: unsafe filename '{filename}' provided.")
                QMessageBox.critical(self, "Save Error",
                                     f"The filename '{filename}' is invalid or contains forbidden characters/patterns.")
                return False

            if os.path.exists(full_save_path):
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

    def prompt_save_changes(self):
        logger.debug("Prompting user to save unsaved changes.")
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "There are unsaved changes in the playlist.\nSave them now?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)
        if reply == QMessageBox.StandardButton.Save:
            logger.info("User chose to Save changes.")
            if self.save_playlist():
                return QMessageBox.StandardButton.Save
            else:
                return QMessageBox.StandardButton.Cancel
        elif reply == QMessageBox.StandardButton.Discard:
            logger.info("User chose to Discard changes.")
            return QMessageBox.StandardButton.Discard
        else:
            logger.info("User chose to Cancel operation.")
            return QMessageBox.StandardButton.Cancel

    def closeEvent(self, event):
        logger.debug("PlaylistEditorWindow closeEvent triggered.")

        if self.text_editor_window_instance and self.text_editor_window_instance.isVisible():
            if not self.text_editor_window_instance.close():
                event.ignore();
                return
        if self.audio_program_editor_instance and self.audio_program_editor_instance.isVisible():
            if not self.audio_program_editor_instance.close():
                event.ignore();
                return
        if self.settings_window_instance and self.settings_window_instance.isVisible():
            self.settings_window_instance.close()

        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore();
                return

        event.accept()
        if event.isAccepted():
            logger.info("PlaylistEditorWindow closing.")
            if self.display_window:
                logger.debug("Clearing display window on PlaylistEditor close.")
                self.display_window.clear_display()