# myapp/gui/playlist_editor.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QListWidget, QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from .file_dialog_helpers import get_themed_open_filename, get_themed_save_filename
from .layer_editor_dialog import LayerEditorDialog
from .settings_window import SettingsWindow
from .text_editor_window import TextEditorWindow
# --- NEW IMPORT FOR AUDIO EDITOR ---
from .audio_program_editor_window import AudioProgramEditorWindow
# --- END NEW IMPORT ---

from ..playlist.playlist import Playlist
from ..utils.paths import get_playlists_path, get_icon_file_path  # Removed get_media_path, get_playlist_file_path
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
        self.setGeometry(100, 100, 700, 600)
        self.setWindowModified(False)
        self.settings_window_instance = None
        self.text_editor_window_instance = None
        self.audio_program_editor_instance = None  # --- NEW INSTANCE VAR ---

        try:
            icon_name = "edit.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                logger.warning(f"PlaylistEditor icon '{icon_name}' not found.")
        except Exception as e:
            logger.error(f"Failed to set PlaylistEditor window icon: {e}", exc_info=True)

        self.setup_ui()
        self.update_title()
        self.populate_list()
        logger.debug("PlaylistEditorWindow initialized.")

    def setup_ui(self):
        logger.debug("Setting up PlaylistEditorWindow UI...")
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # Toolbar: New, Load, Save, Save As, Settings, Done
        toolbar_layout = QHBoxLayout()
        self.new_button = create_button(" New", "new.png", "Create a new playlist", self.new_playlist)
        self.load_button = create_button(" Load", "load.png", "Load an existing playlist", self.load_playlist_dialog)
        self.save_button = create_button(" Save", "save.png", "Save the current playlist", self.save_playlist)
        self.save_as_button = create_button(" Save As...", "save.png", "Save the current playlist under a new name",
                                            self.save_playlist_as)
        self.settings_button = create_button(" Settings", "settings.png", "Application settings",
                                             self.open_settings_window)  # Moved from slide controls
        self.done_button = create_button(" Done", "done.png", "Close the playlist editor", self.close)

        toolbar_layout.addWidget(self.new_button)
        toolbar_layout.addWidget(self.load_button)
        toolbar_layout.addWidget(self.save_button)
        toolbar_layout.addWidget(self.save_as_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.settings_button)
        toolbar_layout.addWidget(self.done_button)
        main_layout.addLayout(toolbar_layout)

        # Playlist items list
        self.playlist_list = QListWidget()
        self.playlist_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.playlist_list.itemDoubleClicked.connect(self.edit_slide_layers_dialog)  # Edit details on double click
        main_layout.addWidget(self.playlist_list)

        # Slide / Content editing controls
        slide_controls_layout = QHBoxLayout()
        self.add_slide_button = create_button(" Add Slide", "add.png", "Add a new slide to the playlist",
                                              self.add_slide)
        self.edit_slide_button = create_button(" Edit Slide Details", "edit.png",
                                               "Edit layers, timing, and text for selected slide",
                                               self.edit_selected_slide_layers)
        self.edit_text_button = create_button(" Edit Text Paragraphs", "text.png", "Open Text Paragraph Editor",
                                              self.open_text_editor)

        # --- NEW AUDIO PROGRAM EDITOR BUTTON ---
        self.edit_audio_programs_button = create_button(" Edit Audio Programs", "audio_icon.png",
                                                        "Open Audio Program Editor", self.open_audio_program_editor)
        # --- END NEW AUDIO PROGRAM EDITOR BUTTON ---

        self.preview_slide_button = create_button(" Preview Slide Images", "preview.png",
                                                  "Preview selected slide's images on display window",
                                                  self.preview_selected_slide)
        self.remove_slide_button = create_button(" Remove Slide", "remove.png", "Remove the selected slide",
                                                 self.remove_slide)

        slide_controls_layout.addWidget(self.add_slide_button)
        slide_controls_layout.addWidget(self.edit_slide_button)
        slide_controls_layout.addWidget(self.edit_text_button)
        slide_controls_layout.addWidget(self.edit_audio_programs_button)  # --- ADDED BUTTON ---
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

        logger.info(f"Opening layer/details editor for slide at index {row}.")
        current_layers = slide_data.get("layers", [])
        current_duration = slide_data.get("duration", 0)
        current_loop_target = slide_data.get("loop_to_slide", 0)
        current_text_overlay = slide_data.get("text_overlay", None)
        # TODO: Later, pass current_audio_program_name from slide_data to LayerEditorDialog if it exists

        editor = LayerEditorDialog(current_layers, current_duration, current_loop_target,
                                   current_text_overlay,  # Pass current text overlay
                                   # current_audio_program_name, # Pass this later
                                   self.display_window, self)

        if editor.exec():
            logger.info(f"Layer/details editor for slide {row} accepted.")
            updated_data = editor.get_updated_slide_data()

            old_text_overlay = slide_data.get("text_overlay")
            new_text_overlay = updated_data.get("text_overlay")
            # TODO: Later, check if audio_program_name changed

            layers_changed = slide_data.get("layers", []) != updated_data["layers"]
            duration_changed = slide_data.get("duration", 0) != updated_data["duration"]
            loop_changed = slide_data.get("loop_to_slide", 0) != updated_data["loop_to_slide"]
            text_overlay_changed = old_text_overlay != new_text_overlay

            if layers_changed or duration_changed or loop_changed or text_overlay_changed:  # Add audio change check later
                logger.info(f"Slide {row} data changed. Updating playlist.")
                slide_data["layers"] = updated_data["layers"]
                slide_data["duration"] = updated_data["duration"]
                slide_data["loop_to_slide"] = updated_data["loop_to_slide"]
                slide_data["text_overlay"] = new_text_overlay
                # slide_data["audio_program_name"] = updated_data.get("audio_program_name") # Add later
                self.playlist.update_slide(row, slide_data)
                self.mark_dirty()
            else:
                logger.info(f"Layer/details editor for slide {row} closed with no changes.")
            self.populate_list()
            self.playlist_list.setCurrentRow(row)
        else:
            logger.info(f"Layer/details editor for slide {row} cancelled.")

    def open_text_editor(self):
        logger.info("Opening text editor window...")
        if self.text_editor_window_instance is None or not self.text_editor_window_instance.isVisible():
            self.text_editor_window_instance = TextEditorWindow(self)
            self.text_editor_window_instance.show()
        else:
            self.text_editor_window_instance.activateWindow()
            self.text_editor_window_instance.raise_()

    # --- NEW METHOD TO OPEN AUDIO PROGRAM EDITOR ---
    def open_audio_program_editor(self):
        logger.info("Opening Audio Program Editor window...")
        if self.audio_program_editor_instance is None or not self.audio_program_editor_instance.isVisible():
            # Potentially pass managers if they are not singletons or easily accessible
            self.audio_program_editor_instance = AudioProgramEditorWindow(self)
            self.audio_program_editor_instance.show()
        else:
            self.audio_program_editor_instance.activateWindow()
            self.audio_program_editor_instance.raise_()

    # --- END NEW METHOD ---

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
        title += " [*]"  # Indicates modified state
        self.setWindowTitle(title)
        logger.debug(f"Window title updated to: {title.replace(' [*]', '')}")

    def populate_list(self):
        logger.debug("Populating playlist list widget.")
        self.playlist_list.clear()
        for i, slide in enumerate(self.playlist.get_slides()):
            layers_str = ", ".join(slide.get("layers", []))
            duration = slide.get("duration", 0)
            loop_target = slide.get("loop_to_slide", 0)
            text_info = slide.get("text_overlay")
            # audio_program_name = slide.get("audio_program_name") # For later

            base_item_text = f"Slide {i + 1}"
            details = []
            if text_info and text_info.get("paragraph_name"):
                details.append(f"Txt: {text_info['paragraph_name']} (Delay: {duration}s)")
                if loop_target > 0 and duration > 0:
                    details.append(f"Loop to S{loop_target}")
            # elif audio_program_name: # For later
            # details.append(f"Audio: {audio_program_name}")
            # if duration > 0: details.append(f"{duration}s after audio") # Or some other logic
            # if loop_target > 0: details.append(f"Loop to S{loop_target}")
            else:  # No text or audio program
                if duration > 0:
                    details.append(f"{duration}s")
                else:
                    details.append("Manual")
                if loop_target > 0 and duration > 0:
                    details.append(f"Loop to S{loop_target}")
                elif loop_target > 0 and duration == 0:
                    details.append(f"Loop to S{loop_target} (inactive)")

            item_text = f"{base_item_text} ({', '.join(details)}): {layers_str if layers_str else '[Empty Slide]'}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, slide)  # Store full slide data
            self.playlist_list.addItem(item)
        logger.info(f"Playlist list populated with {self.playlist_list.count()} items.")

    def update_playlist_from_list_order(self):
        logger.debug("Updating internal playlist order from list widget.")
        new_slides = []
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item:  # Check if item exists
                slide_data = item.data(Qt.ItemDataRole.UserRole)
                if slide_data:  # Check if data exists
                    new_slides.append(slide_data)

        if len(new_slides) != len(self.playlist.get_slides()):  # Basic integrity check
            logger.warning("Mismatch in slide count during reorder. Repopulating.")

        self.playlist.set_slides(new_slides)  # This now sets the full slide objects
        self.mark_dirty()
        self.populate_list()  # Repopulate to ensure consistency if any data was lost/changed
        logger.debug("Internal playlist order updated and list repopulated.")

    def new_playlist(self):
        logger.info("New playlist action triggered.")
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Cancel:
                logger.info("New playlist action cancelled by user at save prompt.")
                return
        self.playlist = Playlist()  # Creates a new empty playlist
        self.populate_list()
        self.update_title()
        self.mark_dirty(False)  # New playlist is not modified
        logger.info("New empty playlist created.")

    def add_slide(self):
        logger.info("Add slide action triggered.")
        self.update_playlist_from_list_order()  # Ensure current order is reflected internally
        new_slide = {"layers": [], "duration": 0, "loop_to_slide": 0, "text_overlay": None}
        self.playlist.add_slide(new_slide)
        self.populate_list()  # Repopulate to show the new slide
        new_slide_index = self.playlist_list.count() - 1
        self.playlist_list.setCurrentRow(new_slide_index)  # Select the new slide
        self.mark_dirty()
        logger.info(f"New slide added at index {new_slide_index}. Opening editor.")
        self.edit_selected_slide_layers()  # Open editor for the new slide

    def remove_slide(self):
        logger.debug("Remove slide action triggered.")
        current_item = self.playlist_list.currentItem()
        if not current_item:
            logger.warning("Remove slide called but no item selected.")
            return
        row = self.playlist_list.row(current_item)

        self.playlist_list.takeItem(row)  # Remove from view first
        self.update_playlist_from_list_order()  # Update model from view
        # self.populate_list() # update_playlist_from_list_order now calls this
        self.mark_dirty()
        logger.info(f"Slide at index {row} removed.")

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
        slide_data = self.playlist.get_slide(row)  # Assuming this gets from the internal list
        if slide_data:
            layers_to_preview = slide_data.get("layers", [])
            logger.info(f"Previewing slide at index {row} with layers: {layers_to_preview}")
            self.display_window.current_text = None  # Clear previous text for image-only preview
            self.display_window.display_images(layers_to_preview)  # This now also clears text via current_text
            if slide_data.get("text_overlay"):
                QMessageBox.information(self, "Text Preview Note",
                                        "Image preview shown. Text overlay appears when slide is played via Control Window.")

    def load_playlist_dialog(self):
        logger.info("Load playlist dialog action triggered.")
        if self.isWindowModified():
            if self.prompt_save_changes() == QMessageBox.StandardButton.Cancel:
                logger.info("Load playlist action cancelled by user at save prompt.")
                return

        file_name = get_themed_open_filename(self, "Load Playlist", self.playlists_base_dir, "JSON Files (*.json)")
        if file_name:
            logger.info(f"User selected playlist file to load: {file_name}")
            try:
                self.playlist.load(file_name)  # Load into the existing playlist object
                self.populate_list()
                self.update_title()
                self.mark_dirty(False)  # Loaded playlist is not considered modified yet
                self.playlist_saved_signal.emit(file_name)  # Signal that a playlist was loaded/saved
                logger.info(f"Successfully loaded playlist: {file_name}")
            except (FileNotFoundError, ValueError) as e:
                logger.error(f"Failed to load playlist '{file_name}': {e}", exc_info=True)
                QMessageBox.critical(self, "Load Error", f"Failed to load playlist: {e}")
        else:
            logger.info("Load playlist dialog cancelled by user.")

    def save_playlist(self):
        logger.info("Save playlist action triggered.")
        self.update_playlist_from_list_order()  # Ensure order is correct
        if not self.playlist.file_path:
            logger.info("Playlist has no current file path, calling Save As...")
            return self.save_playlist_as()
        else:
            logger.info(f"Saving playlist to: {self.playlist.file_path}")
            if self.playlist.save(self.playlist.file_path):
                self.mark_dirty(False)
                QMessageBox.information(self, "Save Success", "Playlist saved.")
                self.playlist_saved_signal.emit(self.playlist.file_path)  # Emit signal with path
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

            # No restriction on saving outside default dir for Save As
            # if os.path.dirname(full_save_path) != self.playlists_base_dir: ...

            if os.path.exists(full_save_path):
                reply = QMessageBox.question(self, "Confirm Overwrite", f"'{filename}' exists. Overwrite?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    logger.info("User chose not to overwrite. Save As cancelled.")
                    return False

            if self.playlist.save(full_save_path):  # This will set self.playlist.file_path
                self.update_title()
                self.mark_dirty(False)
                QMessageBox.information(self, "Save Success", f"Playlist saved as {filename}.")
                self.playlist_saved_signal.emit(full_save_path)  # Emit signal with new path
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
                                     QMessageBox.StandardButton.Save)  # Default to Save

        if reply == QMessageBox.StandardButton.Save:
            logger.info("User chose to Save changes.")
            if self.save_playlist():
                return QMessageBox.StandardButton.Save  # Indicates successful save
            else:
                return QMessageBox.StandardButton.Cancel  # Save failed, treat as cancel
        elif reply == QMessageBox.StandardButton.Discard:
            logger.info("User chose to Discard changes.")
            return QMessageBox.StandardButton.Discard
        else:  # Cancel
            logger.info("User chose to Cancel operation.")
            return QMessageBox.StandardButton.Cancel

    def closeEvent(self, event):
        logger.debug("PlaylistEditorWindow closeEvent triggered.")

        # Close child modal/modeless windows first if they might have unsaved changes
        if self.text_editor_window_instance and self.text_editor_window_instance.isVisible():
            if not self.text_editor_window_instance.close():  # close() should handle its own save prompts
                event.ignore();
                return

        if self.audio_program_editor_instance and self.audio_program_editor_instance.isVisible():
            if not self.audio_program_editor_instance.close():
                event.ignore();
                return

        if self.settings_window_instance and self.settings_window_instance.isVisible():
            self.settings_window_instance.close()  # Settings usually don't need complex save prompts

        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore();
                return

        event.accept()
        if event.isAccepted():
            logger.info("PlaylistEditorWindow closing.")
            if self.display_window:  # Clear display if editor closes
                logger.debug("Clearing display window on PlaylistEditor close.")
                self.display_window.clear_display()