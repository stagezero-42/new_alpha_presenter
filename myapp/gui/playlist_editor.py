# myapp/gui/playlist_editor.py
import os
import logging
import copy  # For deepcopy
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

from ..playlist.playlist import Playlist, get_default_slide_audio_settings  # Import getter
from ..utils.paths import get_playlists_path, get_icon_file_path
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
        self.duplicate_slide_button = create_button(" Duplicate Slide", "duplicate.png",  # NEW BUTTON
                                                    "Duplicate selected slide", self.duplicate_selected_slide)
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
        slide_controls_layout.addWidget(self.duplicate_slide_button)  # NEW
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
            # NEW
            display_window_instance=self.display_window,
            parent=self
        )

        if editor.exec():
            logger.info(f"Layer/details editor for slide {row} accepted.")
            updated_data_from_dialog = editor.get_updated_slide_data()
            changes = {}
            all_keys = ["layers", "duration", "loop_to_slide", "text_overlay",
                        "audio_program_name", "loop_audio_program",
                        "audio_intro_delay_ms", "audio_outro_duration_ms",
                        "audio_program_volume"]  # NEW
            for key in all_keys:
                old_val = slide_data.get(key)
                new_val = updated_data_from_dialog.get(key)
                if key == "text_overlay":
                    old_val = old_val if isinstance(old_val, dict) else {}
                    new_val = new_val if isinstance(new_val, dict) else {}
                if old_val != new_val:
                    changes[key] = {"old": old_val, "new": new_val}

            if changes:
                logger.info(f"Slide {row} data changed. Updating playlist. Changes: {changes}")
                slide_data.update(updated_data_from_dialog)
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

            audio_program_name = slide.get("audio_program_name")
            loop_audio = slide.get("loop_audio_program", False)
            audio_intro_ms = slide.get("audio_intro_delay_ms", 0)
            audio_outro_ms = slide.get("audio_outro_duration_ms", 0)
            audio_volume = slide.get("audio_program_volume", get_default_slide_audio_settings()["audio_program_volume"])

            base_item_text = f"Slide {i + 1}"
            details = []

            if audio_program_name:
                audio_detail = f"Audio: {audio_program_name}"
                if loop_audio: audio_detail += " (Loop)"
                if audio_intro_ms > 0: audio_detail += f", Intro: {audio_intro_ms / 1000.0:.1f}s"
                if audio_outro_ms > 0: audio_detail += f", Outro: {audio_outro_ms / 1000.0:.1f}s"
                if audio_volume != get_default_slide_audio_settings()[
                    "audio_program_volume"]:  # Only show if not default
                    audio_detail += f", Vol: {int(audio_volume * 100)}%"
                details.append(audio_detail)

            if text_info and text_info.get("paragraph_name"):
                text_detail = f"Txt: {text_info['paragraph_name']}"
                if text_info.get("sentence_timing_enabled", False):
                    text_detail += f" (Timed, Delay: {duration}s)"
                elif duration > 0:
                    text_detail += f" (Delay: {duration}s)"
                else:
                    text_detail += " (Manual Text)"
                details.append(text_detail)
            elif not audio_program_name and duration > 0:
                details.append(f"Duration: {duration}s")
            elif not audio_program_name and not (text_info and text_info.get("paragraph_name")):
                details.append("Manual Advance")

            if loop_target > 0:
                is_slide_timed_for_loop = duration > 0 or (text_info and text_info.get("sentence_timing_enabled"))
                if is_slide_timed_for_loop:
                    details.append(f"Loop Slide to S{loop_target}")
                else:
                    details.append(f"Loop Slide to S{loop_target} (Inactive)")

            item_text = f"{base_item_text} ({', '.join(details)}): {layers_str if layers_str else '[Empty Slide]'}"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, slide)
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
            changed_order = True

        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item:
                slide_data = item.data(Qt.ItemDataRole.UserRole)
                new_slides.append(slide_data)
                if not changed_order and (
                        i >= len(current_playlist_slides) or current_playlist_slides[i] != slide_data):
                    changed_order = True
            else:
                logger.error(f"Missing item at index {i} in playlist_list during reorder.")
                changed_order = True;
                break

        if changed_order:
            self.playlist.set_slides(new_slides)
            self.mark_dirty()
            logger.debug("Internal playlist order updated.")

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

        # Create a deep copy to ensure nested structures like text_overlay are also copied
        duplicated_slide_data = copy.deepcopy(original_slide_data)

        self.update_playlist_from_list_order()  # Ensure current order is reflected in model

        insert_index = row + 1
        self.playlist.insert_slide(insert_index, duplicated_slide_data)  # Uses new method in Playlist

        self.populate_list()
        self.playlist_list.setCurrentRow(insert_index)  # Select the new duplicate
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
            layers_to_preview = slide_data.get("layers", [])
            logger.info(f"Previewing slide at index {row} with layers: {layers_to_preview}")
            self.display_window.current_text = None
            if hasattr(self.display_window, 'slide_audio_player') and self.display_window.slide_audio_player:
                self.display_window.slide_audio_player.stop()
            self.display_window.display_images(layers_to_preview)

            preview_notes = ["Image preview shown."]
            if slide_data.get("text_overlay"):
                preview_notes.append("Text overlay appears when slide is played via Control Window.")
            if slide_data.get("audio_program_name"):
                preview_notes.append(
                    "Audio program (with any intro/outro/volume) plays when slide is run via Control Window.")
            QMessageBox.information(self, "Preview Note", "\n".join(preview_notes))

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