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
from .audio_program_editor_window import AudioProgramEditorWindow

from ..playlist.playlist import Playlist
from ..utils.paths import get_playlists_path, get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)


class PlaylistEditorWindow(QMainWindow):
    playlist_saved_signal = Signal(str)  # Emitted with playlist path on save/load

    def __init__(self, display_window_instance, playlist_obj, parent=None):
        super().__init__(parent)
        logger.debug(
            f"Initializing PlaylistEditorWindow. Current playlist has {len(playlist_obj.get_slides())} slides.")
        self.base_title = "Playlist Editor"
        self.display_window = display_window_instance
        self.playlist = playlist_obj  # This is a Playlist object
        self.playlists_base_dir = get_playlists_path()

        self.setWindowTitle(f"{self.base_title} [*]")
        self.setGeometry(100, 100, 700, 600)
        self.setWindowModified(False)
        self.settings_window_instance = None
        self.text_editor_window_instance = None
        self.audio_program_editor_instance = None

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
        # ... (toolbar setup remains the same) ...
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
        main_layout.addWidget(self.playlist_list)

        slide_controls_layout = QHBoxLayout()
        self.add_slide_button = create_button(" Add Slide", "add.png", "Add a new slide", self.add_slide)
        self.edit_slide_button = create_button(" Edit Slide Details", "edit.png", "Edit selected slide",
                                               self.edit_selected_slide_layers)
        self.edit_text_button = create_button(" Edit Text Paragraphs", "text.png", "Open Text Editor",
                                              self.open_text_editor)
        self.edit_audio_programs_button = create_button(" Edit Audio Programs", "audio_icon.png",
                                                        "Open Audio Program Editor", self.open_audio_program_editor)
        self.preview_slide_button = create_button(" Preview Slide Images", "preview.png",
                                                  "Preview selected slide images", self.preview_selected_slide)
        self.remove_slide_button = create_button(" Remove Slide", "remove.png", "Remove selected slide",
                                                 self.remove_slide)

        slide_controls_layout.addWidget(self.add_slide_button)
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
        slide_data = self.playlist.get_slide(row)  # Get current data from Playlist object
        if not slide_data:
            logger.error(f"Could not retrieve slide data for row {row} during edit.")
            return

        logger.info(f"Opening layer/details editor for slide at index {row}.")
        # --- PASS AUDIO DATA TO DIALOG ---
        editor = LayerEditorDialog(
            slide_layers=slide_data.get("layers", []),
            current_duration=slide_data.get("duration", 0),
            current_loop_target=slide_data.get("loop_to_slide", 0),
            current_text_overlay=slide_data.get("text_overlay"),
            current_audio_program_name=slide_data.get("audio_program_name"),
            current_loop_audio_program=slide_data.get("loop_audio_program", False),
            display_window_instance=self.display_window,
            parent=self
        )
        # --- END PASS AUDIO DATA ---

        if editor.exec():
            logger.info(f"Layer/details editor for slide {row} accepted.")
            updated_data_from_dialog = editor.get_updated_slide_data()

            # Create a dictionary of changes for logging/comparison
            changes = {}
            for key in ["layers", "duration", "loop_to_slide", "text_overlay", "audio_program_name",
                        "loop_audio_program"]:
                old_val = slide_data.get(key)
                new_val = updated_data_from_dialog.get(key)
                # Handle text_overlay specially for comparison if it can be None vs {}
                if key == "text_overlay":
                    old_val = old_val if isinstance(old_val, dict) else {}
                    new_val = new_val if isinstance(new_val, dict) else {}
                if old_val != new_val:
                    changes[key] = {"old": old_val, "new": new_val}

            if changes:
                logger.info(f"Slide {row} data changed. Updating playlist. Changes: {changes}")
                # Update the slide_data dictionary directly with all new values
                slide_data.update(updated_data_from_dialog)
                self.playlist.update_slide(row, slide_data)  # Pass the modified slide_data
                self.mark_dirty()
            else:
                logger.info(f"Layer/details editor for slide {row} closed with no changes.")

            self.populate_list()  # Repopulate to reflect any changes
            self.playlist_list.setCurrentRow(row)  # Re-select the edited row
        else:
            logger.info(f"Layer/details editor for slide {row} cancelled.")

    # ... (open_text_editor, open_audio_program_editor, open_settings_window, mark_dirty, update_title remain the same) ...
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
            layers_str = ", ".join(slide.get("layers", []))
            duration = slide.get("duration", 0)
            loop_target = slide.get("loop_to_slide", 0)
            text_info = slide.get("text_overlay")
            # --- NEW: Get audio info ---
            audio_program_name = slide.get("audio_program_name")
            loop_audio = slide.get("loop_audio_program", False)
            # --- END NEW ---

            base_item_text = f"Slide {i + 1}"
            details = []

            if audio_program_name:
                audio_detail = f"Audio: {audio_program_name}"
                if loop_audio:
                    audio_detail += " (Loop)"
                details.append(audio_detail)

            if text_info and text_info.get("paragraph_name"):
                text_detail = f"Txt: {text_info['paragraph_name']}"
                if text_info.get("sentence_timing_enabled", False):
                    text_detail += f" (Timed, Delay: {duration}s)"
                elif duration > 0:  # Text exists, not timed, but slide has initial delay for text
                    text_detail += f" (Delay: {duration}s)"
                else:  # Text exists, not timed, no initial delay
                    text_detail += " (Manual Text)"
                details.append(text_detail)
            elif not audio_program_name:  # Only show slide duration if no audio and no text
                if duration > 0:
                    details.append(f"Duration: {duration}s")
                else:
                    details.append("Manual Advance")

            if loop_target > 0:  # Slide loop target
                # A slide loop is typically only meaningful if there's a duration (either slide duration or text timing implies some duration)
                is_slide_timed_for_loop = duration > 0 or (text_info and text_info.get("sentence_timing_enabled"))
                if is_slide_timed_for_loop:
                    details.append(f"Loop Slide to S{loop_target}")
                else:
                    details.append(f"Loop Slide to S{loop_target} (Inactive)")

            item_text = f"{base_item_text} ({', '.join(details)}): {layers_str if layers_str else '[Empty Slide]'}"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, slide)  # Store the slide dict itself
            self.playlist_list.addItem(list_item)

        if 0 <= current_row < self.playlist_list.count():
            self.playlist_list.setCurrentRow(current_row)
        elif self.playlist_list.count() > 0:
            self.playlist_list.setCurrentRow(0)

        logger.info(f"Playlist list populated with {self.playlist_list.count()} items.")

    def update_playlist_from_list_order(self):
        logger.debug("Updating internal playlist order from list widget.")
        new_slides = []
        changed_order = False
        current_playlist_slides = self.playlist.get_slides()

        if self.playlist_list.count() != len(current_playlist_slides):
            changed_order = True  # Count mismatch implies change

        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item:
                slide_data = item.data(Qt.ItemDataRole.UserRole)
                new_slides.append(slide_data)
                if not changed_order and (
                        i >= len(current_playlist_slides) or current_playlist_slides[i] != slide_data):
                    changed_order = True
            else:  # Should not happen if list is populated correctly
                logger.error(f"Missing item at index {i} in playlist_list during reorder.")
                changed_order = True  # Consider it a change to be safe
                break

        if changed_order:
            self.playlist.set_slides(new_slides)
            self.mark_dirty()
            logger.debug("Internal playlist order updated.")
        # No need to repopulate here if only order changed, but other ops might require it.
        # self.populate_list() # If data integrity might be affected beyond order

    def new_playlist(self):
        logger.info("New playlist action triggered.")
        if self.isWindowModified():
            reply = self.prompt_save_changes()  # Uses QMessageBox.StandardButton enums
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
        # --- NEW: Default audio for new slide ---
        new_slide_data = {
            "layers": [], "duration": 0, "loop_to_slide": 0, "text_overlay": None,
            "audio_program_name": None, "loop_audio_program": False
        }
        # --- END NEW ---
        self.playlist.add_slide(new_slide_data)
        self.populate_list()
        new_slide_index = self.playlist_list.count() - 1
        self.playlist_list.setCurrentRow(new_slide_index)
        self.mark_dirty()
        logger.info(f"New slide added at index {new_slide_index}. Opening editor.")
        self.edit_selected_slide_layers()

    # ... (remove_slide, edit_selected_slide_layers, preview_selected_slide, load_playlist_dialog, save_playlist, save_playlist_as, prompt_save_changes, closeEvent remain largely the same but ensure they use self.playlist which is a Playlist object) ...
    def remove_slide(self):
        logger.debug("Remove slide action triggered.")
        current_item = self.playlist_list.currentItem()
        if not current_item:
            logger.warning("Remove slide called but no item selected.")
            return
        row = self.playlist_list.row(current_item)

        # Order of operations:
        # 1. Remove from the QListWidget view
        self.playlist_list.takeItem(row)
        # 2. Update the internal playlist model based on the new view order
        #    This also handles marking as dirty if the order or content changes.
        self.update_playlist_from_list_order()
        # 3. Repopulate to ensure consistency if update_playlist_from_list_order doesn't do it fully
        #    (or if there are subtle data changes not caught by simple reordering logic)
        # self.populate_list() # update_playlist_from_list_order should handle marking dirty. This might be redundant unless data changes.
        # For safety and to ensure list reflects true model state after any complex update:
        self.populate_list()  # Re-sync list from model
        self.mark_dirty()  # Ensure dirty flag is set from remove operation itself

        logger.info(f"Slide at index {row} removed.")
        # If list is not empty, select a new item
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
            layers_to_preview = slide_data.get("layers", [])
            logger.info(f"Previewing slide at index {row} with layers: {layers_to_preview}")
            self.display_window.current_text = None
            # Stop any slide-specific audio from ControlWindow's player during preview
            if hasattr(self.display_window, 'slide_audio_player') and self.display_window.slide_audio_player:
                self.display_window.slide_audio_player.stop()
            self.display_window.display_images(layers_to_preview)

            preview_notes = ["Image preview shown."]
            if slide_data.get("text_overlay"):
                preview_notes.append("Text overlay appears when slide is played via Control Window.")
            if slide_data.get("audio_program_name"):
                preview_notes.append("Audio program plays when slide is run via Control Window.")
            QMessageBox.information(self, "Preview Note", "\n".join(preview_notes))

    def load_playlist_dialog(self):
        logger.info("Load playlist dialog action triggered.")
        if self.isWindowModified():
            reply = self.prompt_save_changes()
            if reply == QMessageBox.StandardButton.Cancel:  # Check for actual cancel
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
                # QMessageBox.information(self, "Save Success", "Playlist saved.") # Optional, can be verbose
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
            else:  # Save failed
                return QMessageBox.StandardButton.Cancel  # Treat failed save as a cancel of the close op
        elif reply == QMessageBox.StandardButton.Discard:
            logger.info("User chose to Discard changes.")
            return QMessageBox.StandardButton.Discard
        else:  # Cancel
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