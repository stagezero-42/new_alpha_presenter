# myapp/gui/text_editor_window.py
import os
import logging
import copy  # For deepcopy in duplicate_paragraph
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QMessageBox, QInputDialog,
    QSplitter, QLabel, QGroupBox, QTextEdit, QTableWidget,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

# Local Imports
from ..text.paragraph_manager import ParagraphManager
from ..utils.paths import get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component
from .sentence_manager import SentenceManager
from .text_import_dialog import TextImportDialog

logger = logging.getLogger(__name__)


class TextEditorWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Initializing TextEditorWindow...")
        self.setWindowTitle("Text Paragraph Editor [*]")
        self.setGeometry(150, 150, 900, 700)
        self.setWindowModified(False)

        self.paragraph_manager = ParagraphManager()
        self.paragraphs_cache = {}
        self.current_paragraph_name = None
        self._block_list_signals = False

        self._setup_ui()

        self.sentence_manager = SentenceManager(self, self.sent_table_widget, self.sent_edit_text)
        self.sentence_manager.sentences_updated.connect(lambda: self.mark_dirty(True))

        self.load_and_list_paragraphs()
        self.update_ui_state()
        logger.debug("TextEditorWindow initialized.")

    def _setup_ui(self):
        logger.debug("Setting up TextEditorWindow UI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._setup_paragraph_panel(splitter)
        self._setup_sentence_panel(splitter)

        splitter.setSizes([250, 650])
        main_layout.addWidget(splitter)
        logger.debug("TextEditorWindow UI setup complete.")

    def _setup_paragraph_panel(self, splitter):
        """Sets up the left panel for paragraph listing and management."""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Paragraphs:"))

        self.para_list_widget = QListWidget()
        self.para_list_widget.currentItemChanged.connect(self.handle_para_selection_changed)
        left_layout.addWidget(self.para_list_widget)

        para_buttons_layout_row1 = QHBoxLayout()
        self.add_para_button = create_button("Add", "add.png", "Add New Paragraph", self.add_paragraph)
        self.import_para_button = create_button("Import", "import.png", "Import Text File",
                                                self.open_text_import_dialog)
        self.rename_para_button = create_button("Rename", "edit.png", "Rename Selected Paragraph",
                                                self.rename_paragraph)

        para_buttons_layout_row1.addWidget(self.add_para_button)
        para_buttons_layout_row1.addWidget(self.import_para_button)
        para_buttons_layout_row1.addWidget(self.rename_para_button)
        left_layout.addLayout(para_buttons_layout_row1)

        para_buttons_layout_row2 = QHBoxLayout()
        self.duplicate_para_button = create_button("Duplicate", "duplicate.png",  # NEW
                                                   "Duplicate Selected Paragraph", self.duplicate_paragraph)
        self.del_para_button = create_button("Delete", "remove.png", "Delete Selected Paragraph", self.delete_paragraph)
        para_buttons_layout_row2.addWidget(self.duplicate_para_button)
        para_buttons_layout_row2.addStretch()  # Add stretch to push delete to the right if desired
        para_buttons_layout_row2.addWidget(self.del_para_button)
        left_layout.addLayout(para_buttons_layout_row2)

        splitter.addWidget(left_widget)

    def _setup_sentence_panel(self, splitter):
        """Sets up the right panel for sentence editing."""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        top_right_buttons_layout = QHBoxLayout()
        top_right_buttons_layout.addStretch()
        self.save_button = create_button("Save All Changes", "save.png", on_click=self.save_all_changes)
        self.done_button = create_button("Done", "done.png", on_click=self.close)
        top_right_buttons_layout.addWidget(self.save_button)
        top_right_buttons_layout.addWidget(self.done_button)
        right_layout.addLayout(top_right_buttons_layout)

        self.para_group_box = QGroupBox("Edit Sentences")
        group_layout = QVBoxLayout(self.para_group_box)
        self.para_name_label = QLabel("Paragraph: (None)")
        self.para_name_label.setStyleSheet("font-weight: bold;")
        group_layout.addWidget(self.para_name_label)
        group_layout.addWidget(QLabel("Sentences (Drag Row Header to Reorder):"))

        self.sent_table_widget = QTableWidget()
        self.sent_table_widget.setColumnCount(2)
        self.sent_table_widget.setHorizontalHeaderLabels(["Sentence Text", "Duration (s)"])
        self.sent_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.sent_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.sent_table_widget.verticalHeader().setSectionsMovable(True)
        self.sent_table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sent_table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        group_layout.addWidget(self.sent_table_widget)

        sent_buttons_layout1 = QHBoxLayout()
        self.add_sent_button = create_button("Add", "add.png", "Add Sentence",
                                             lambda: self.sentence_manager.add_sentence())
        self.duplicate_sent_button = create_button("Duplicate", "duplicate.png",  # NEW
                                                   "Duplicate Selected Sentence",
                                                   lambda: self.sentence_manager.duplicate_sentence())
        self.del_sent_button = create_button("Remove", "remove.png", "Remove Selected Sentence",
                                             lambda: self.sentence_manager.delete_sentence())
        sent_buttons_layout1.addWidget(self.add_sent_button)
        sent_buttons_layout1.addWidget(self.duplicate_sent_button)  # NEW
        sent_buttons_layout1.addWidget(self.del_sent_button)
        sent_buttons_layout1.addStretch()
        group_layout.addLayout(sent_buttons_layout1)

        sent_buttons_layout2 = QHBoxLayout()
        sent_buttons_layout2.addStretch()
        self.split_sent_button = create_button("Split", "split.png", "Split Sentence at Cursor",
                                               lambda: self.sentence_manager.split_sentence())
        self.join_sent_button = create_button("Join", "join.png", "Join Selected Sentence with Next",
                                              lambda: self.sentence_manager.join_sentence())
        self.blank_sent_button = create_button("Blank", "blank.png",  # NEW (using placeholder icon)
                                               "Insert Blank Sentence After Selected",
                                               lambda: self.sentence_manager.insert_blank_sentence())
        sent_buttons_layout2.addWidget(self.split_sent_button)
        sent_buttons_layout2.addWidget(self.join_sent_button)
        sent_buttons_layout2.addWidget(self.blank_sent_button)  # NEW
        group_layout.addLayout(sent_buttons_layout2)

        group_layout.addWidget(QLabel("Edit Selected Sentence Text:"))
        self.sent_edit_text = QTextEdit()
        group_layout.addWidget(self.sent_edit_text)

        right_layout.addWidget(self.para_group_box)
        splitter.addWidget(right_widget)

        self._set_window_icon()

    def _set_window_icon(self):
        try:
            icon_path = get_icon_file_path("text.png") or get_icon_file_path("edit.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set TextEditorWindow icon: {e}", exc_info=True)

    def open_text_import_dialog(self):
        logger.debug("Open text import dialog called.")
        import_dialog = TextImportDialog(self, self.paragraph_manager)
        import_dialog.paragraph_imported.connect(self._handle_paragraph_imported)
        import_dialog.exec()

    def _handle_paragraph_imported(self, new_paragraph_name):
        logger.info(f"Paragraph '{new_paragraph_name}' was imported/created. Refreshing list.")
        self.load_and_list_paragraphs(select_program_name=new_paragraph_name)
        # For newly created/imported paragraphs, they are saved to disk, so no "dirty" state for that specific item.
        # However, other paragraphs might be dirty. The window's dirty state handles overall changes.
        # If the action was 'add', it's saved, so that specific item isn't dirty.
        # If only this action happened, window might not be dirty overall.
        # self.mark_dirty(False) # This might be too aggressive if other changes exist.

    def mark_dirty(self, dirty=True):
        self.setWindowModified(dirty)
        self.update_ui_state()

    def load_and_list_paragraphs(self, select_program_name=None):  # Renamed param for clarity
        logger.debug(f"Loading and listing paragraphs. Target selection: '{select_program_name}'")
        current_selection_name = select_program_name if select_program_name else self.current_paragraph_name

        self._block_list_signals = True
        self.para_list_widget.clear()
        self._block_list_signals = False

        try:
            para_names = sorted(self.paragraph_manager.list_paragraphs())
            if not para_names:
                self.current_paragraph_name = None
                if self.sentence_manager: self.sentence_manager.set_current_paragraph(None, None)
                self.para_name_label.setText("Paragraph: (None)")
                self.update_ui_state()
                return

            self.para_list_widget.addItems(para_names)

            restored_selection = False
            if current_selection_name and current_selection_name in para_names:
                for i in range(self.para_list_widget.count()):
                    if self.para_list_widget.item(i).text() == current_selection_name:
                        self.para_list_widget.setCurrentRow(i)
                        restored_selection = True
                        break

            if not restored_selection and self.para_list_widget.count() > 0:
                self.para_list_widget.setCurrentRow(0)

            # Explicitly call handler if selection logic didn't trigger it or list is now empty
            if self.para_list_widget.currentItem():
                self.handle_para_selection_changed(self.para_list_widget.currentItem(), None)
            else:  # List is empty or became empty
                self.handle_para_selection_changed(None, None)


        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to list paragraphs: {e}")
            self.current_paragraph_name = None
            if self.sentence_manager: self.sentence_manager.set_current_paragraph(None, None)
            self.para_name_label.setText("Paragraph: (None)")

        self.update_ui_state()

    def handle_para_selection_changed(self, current_item, previous_item):
        if self._block_list_signals: return

        if not current_item:
            self.current_paragraph_name = None
            if self.sentence_manager: self.sentence_manager.set_current_paragraph(None, None)
            self.para_name_label.setText("Paragraph: (None)")
            self.update_ui_state()
            return

        selected_para_name = current_item.text()

        if selected_para_name == self.current_paragraph_name and self.current_paragraph_name in self.paragraphs_cache:
            if self.sentence_manager:
                self.sentence_manager.set_current_paragraph(
                    self.current_paragraph_name,
                    self.paragraphs_cache[self.current_paragraph_name]
                )
            self.update_ui_state()
            return

        self.current_paragraph_name = selected_para_name
        logger.info(f"Paragraph selected: {self.current_paragraph_name}")

        if self.current_paragraph_name not in self.paragraphs_cache:
            try:
                self.paragraphs_cache[self.current_paragraph_name] = \
                    self.paragraph_manager.load_paragraph(self.current_paragraph_name)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load '{self.current_paragraph_name}': {e}")
                self.paragraphs_cache.pop(self.current_paragraph_name, None)
                # Try to select a different item or clear selection
                current_row = self.para_list_widget.currentRow()
                self.para_list_widget.takeItem(current_row)  # Remove problematic item
                if self.para_list_widget.count() > 0:
                    self.para_list_widget.setCurrentRow(0)
                else:  # List is now empty
                    self.current_paragraph_name = None  # Ensure this is None
                    self.handle_para_selection_changed(None, None)  # Recurse to handle empty state
                return  # Avoid further processing for the failed item

        if self.current_paragraph_name and self.current_paragraph_name in self.paragraphs_cache:
            if self.sentence_manager: self.sentence_manager.set_current_paragraph(
                self.current_paragraph_name,
                self.paragraphs_cache[self.current_paragraph_name]
            )
            self.para_name_label.setText(f"Paragraph: {self.current_paragraph_name}")
        else:
            if self.sentence_manager: self.sentence_manager.set_current_paragraph(None, None)
            self.para_name_label.setText("Paragraph: (None)")
        self.update_ui_state()

    def add_paragraph(self):
        para_name, ok = QInputDialog.getText(self, "New Paragraph", "Enter name:")
        if ok and para_name:
            safe_name = para_name.strip().replace(" ", "_")
            if not is_safe_filename_component(f"{safe_name}.json"):
                QMessageBox.warning(self, "Invalid Name", "Name contains invalid characters or is reserved.");
                return
            if safe_name in self.paragraph_manager.list_paragraphs():
                QMessageBox.warning(self, "Name Exists", "A paragraph with this name already exists.");
                return

            new_para_data = {"name": safe_name, "sentences": []}
            if self.paragraph_manager.save_paragraph(safe_name, new_para_data):
                self.paragraphs_cache[safe_name] = new_para_data  # Cache it
                self._handle_paragraph_imported(safe_name)
            else:
                QMessageBox.critical(self, "Save Error", "Could not save the new paragraph.")

    def duplicate_paragraph(self):
        if not self.current_paragraph_name:
            QMessageBox.information(self, "Duplicate Paragraph", "Please select a paragraph to duplicate.")
            return

        original_name = self.current_paragraph_name
        try:
            original_data = self.paragraphs_cache.get(original_name)
            if not original_data:  # Should not happen if selection is valid
                original_data = self.paragraph_manager.load_paragraph(original_name)
            if not original_data:  # Still no data
                QMessageBox.critical(self, "Error", f"Could not load data for '{original_name}'.")
                return

            # Determine unique new name
            base_name = original_name
            count = 1
            new_name = f"{base_name}_{count:02d}"
            existing_names = self.paragraph_manager.list_paragraphs()
            while new_name in existing_names:
                count += 1
                new_name = f"{base_name}_{count:02d}"

            logger.info(f"Duplicating paragraph '{original_name}' to '{new_name}'.")

            new_paragraph_data = copy.deepcopy(original_data)
            new_paragraph_data["name"] = new_name

            if self.paragraph_manager.save_paragraph(new_name, new_paragraph_data):
                self.paragraphs_cache[new_name] = new_paragraph_data
                self._handle_paragraph_imported(new_name)  # Refresh list and select
                QMessageBox.information(self, "Paragraph Duplicated",
                                        f"Paragraph '{original_name}' duplicated as '{new_name}'.")
            else:
                QMessageBox.critical(self, "Save Error", f"Could not save the duplicated paragraph '{new_name}'.")

        except Exception as e:
            logger.error(f"Error duplicating paragraph '{original_name}': {e}", exc_info=True)
            QMessageBox.critical(self, "Duplicate Error", f"An error occurred: {e}")

    def rename_paragraph(self):
        current_list_item = self.para_list_widget.currentItem()
        if not current_list_item or not self.current_paragraph_name: return

        old_name = self.current_paragraph_name
        new_name_input, ok = QInputDialog.getText(self, "Rename Paragraph", f"New name for '{old_name}':",
                                                  text=old_name)

        if ok and new_name_input and new_name_input.strip():
            safe_new_name = new_name_input.strip().replace(" ", "_")
            if safe_new_name == old_name: return

            if not is_safe_filename_component(f"{safe_new_name}.json"):
                QMessageBox.warning(self, "Invalid Name", "New name contains invalid characters or is reserved.");
                return

            existing_names_lower = [name.lower() for name in self.paragraph_manager.list_paragraphs() if
                                    name.lower() != old_name.lower()]
            if safe_new_name.lower() in existing_names_lower:
                QMessageBox.warning(self, "Name Exists", "A paragraph with the new name already exists.");
                return
            try:
                current_data = self.paragraphs_cache.get(old_name)
                if not current_data:
                    current_data = self.paragraph_manager.load_paragraph(old_name)

                current_data["name"] = safe_new_name

                if self.paragraph_manager.save_paragraph(safe_new_name, current_data):
                    if old_name.lower() != safe_new_name.lower():  # Only delete if name actually changed (case-insensitively for safety on some FS)
                        self.paragraph_manager.delete_paragraph(old_name)

                    if old_name in self.paragraphs_cache:
                        del self.paragraphs_cache[old_name]
                    self.paragraphs_cache[safe_new_name] = current_data

                    self._handle_paragraph_imported(safe_new_name)
                else:
                    current_data["name"] = old_name  # Revert if save failed
                    QMessageBox.critical(self, "Save Error", "Could not save paragraph with the new name.")
            except Exception as e:
                QMessageBox.critical(self, "Rename Error", f"Failed to rename paragraph: {e}")

    def delete_paragraph(self):
        if not self.current_paragraph_name: return
        para_name_to_delete = self.current_paragraph_name

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete '{para_name_to_delete}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.paragraph_manager.delete_paragraph(para_name_to_delete):
                if para_name_to_delete in self.paragraphs_cache:
                    del self.paragraphs_cache[para_name_to_delete]

                self.current_paragraph_name = None  # Clear current selection before reloading
                self.load_and_list_paragraphs()  # Refresh list, will select first or none
            else:
                QMessageBox.critical(self, "Delete Error", "Could not delete the paragraph file.")

    def save_all_changes(self):
        logger.info("Saving all changes...")
        if not self.isWindowModified():
            QMessageBox.information(self, "No Changes", "No changes to save.");
            return

        saved_count, failed_count = 0, 0
        for name in list(self.paragraphs_cache.keys()):  # list() for safe iteration if cache modified
            data = self.paragraphs_cache[name]
            if data:  # Should always be true if in cache keys
                try:
                    if data.get("name") != name:
                        logger.warning(f"Correcting internal name for '{name}' before saving.")
                        data["name"] = name
                    if self.paragraph_manager.save_paragraph(name, data):
                        saved_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error saving paragraph '{name}': {e}", exc_info=True)
                    failed_count += 1

        if failed_count > 0:
            QMessageBox.warning(self, "Save Error", f"Failed to save {failed_count} paragraph(s). Check logs.")
        if saved_count > 0:
            QMessageBox.information(self, "Save Complete", f"Successfully saved {saved_count} paragraph(s).")

        if failed_count == 0:  # Only mark as not dirty if all saves succeeded
            self.mark_dirty(False)
        else:
            QMessageBox.information(self, "Save Status",
                                    "Some changes might not have been saved. Window remains marked as modified.")

    def update_ui_state(self):
        """Updates the enabled/disabled state of UI elements."""
        para_selected = self.current_paragraph_name is not None

        sent_selected_row = -1
        num_sentences = 0
        if self.sentence_manager:
            sent_selected_row = self.sentence_manager.get_selected_row()
            num_sentences = self.sentence_manager.get_current_sentence_count()

        sent_selected = para_selected and sent_selected_row != -1

        self.rename_para_button.setEnabled(para_selected)
        self.del_para_button.setEnabled(para_selected)
        self.duplicate_para_button.setEnabled(para_selected)  # NEW
        self.para_group_box.setEnabled(para_selected)

        self.add_sent_button.setEnabled(para_selected)
        self.del_sent_button.setEnabled(sent_selected)
        self.duplicate_sent_button.setEnabled(sent_selected)  # NEW

        can_split = sent_selected and self.sent_edit_text.isEnabled() and len(self.sent_edit_text.toPlainText()) > 0
        self.split_sent_button.setEnabled(can_split)

        is_last_sentence = (sent_selected_row == num_sentences - 1) if num_sentences > 0 and sent_selected else False
        can_join = sent_selected and (num_sentences > 1 and not is_last_sentence)
        self.join_sent_button.setEnabled(can_join)
        self.blank_sent_button.setEnabled(para_selected)  # NEW - enable if paragraph selected

        self.sent_edit_text.setEnabled(sent_selected)
        self.save_button.setEnabled(self.isWindowModified())

    def prompt_save_changes(self):
        """Prompts the user to save changes if the window is modified. Returns True if safe to proceed."""
        if not self.isWindowModified():
            return True
        reply = QMessageBox.question(self, 'Unsaved Changes', "There are unsaved changes. Save them now?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)
        if reply == QMessageBox.StandardButton.Save:
            self.save_all_changes()
            return not self.isWindowModified()  # True if save succeeded and cleared dirty flag
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        else:  # Cancel
            return False

    def closeEvent(self, event):
        logger.debug("TextEditorWindow closeEvent triggered.")
        if self.prompt_save_changes():
            event.accept()
            logger.info("TextEditorWindow closing.")
        else:
            event.ignore()
            logger.info("TextEditorWindow close cancelled by user.")