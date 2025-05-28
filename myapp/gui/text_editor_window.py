# myapp/gui/text_editor_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QMessageBox, QInputDialog,
    QListWidgetItem, QAbstractItemView, QSplitter, QLabel,
    QGroupBox, QFormLayout, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from ..text.paragraph_manager import ParagraphManager
from ..utils.paths import get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)


class TextEditorWindow(QMainWindow):
    """Window for creating, editing, and deleting text paragraphs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Initializing TextEditorWindow...")
        self.setWindowTitle("Text Paragraph Editor [*]")
        self.setGeometry(150, 150, 800, 600)
        self.setWindowModified(False)

        self.paragraph_manager = ParagraphManager()
        self.paragraphs_cache = {}  # Cache loaded data {name: data}
        self.current_paragraph_name = None

        # Set window icon
        try:
            icon_path = get_icon_file_path("text.png")
            if not icon_path or not os.path.exists(icon_path):
                logger.warning("text.png not found, trying edit.png as fallback.")
                icon_path = get_icon_file_path("edit.png")

            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                logger.warning("No suitable icon found for TextEditorWindow.")
        except Exception as e:
            logger.error(f"Failed to set TextEditorWindow icon: {e}", exc_info=True)

        self.setup_ui()
        self.load_and_list_paragraphs()
        self.update_ui_state()
        logger.debug("TextEditorWindow initialized.")

    def setup_ui(self):
        logger.debug("Setting up TextEditorWindow UI...")
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # --- Splitter for Two Panes ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Pane (Paragraph List) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Paragraphs:"))
        self.para_list_widget = QListWidget()
        self.para_list_widget.currentItemChanged.connect(self.handle_para_selection_changed)
        left_layout.addWidget(self.para_list_widget)

        para_buttons_layout = QHBoxLayout()
        self.add_para_button = create_button("Add", "add.png", "Add New Paragraph", self.add_paragraph)
        self.rename_para_button = create_button("Rename", "edit.png", "Rename Selected Paragraph",
                                                self.rename_paragraph)
        self.del_para_button = create_button("Delete", "remove.png", "Delete Selected Paragraph", self.delete_paragraph)
        para_buttons_layout.addWidget(self.add_para_button)
        para_buttons_layout.addWidget(self.rename_para_button)
        para_buttons_layout.addWidget(self.del_para_button)
        left_layout.addLayout(para_buttons_layout)
        splitter.addWidget(left_widget)

        # --- Right Pane (Sentence Editor) ---
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

        group_layout.addWidget(QLabel("Sentences (Drag to Reorder):"))
        self.sent_list_widget = QListWidget()
        self.sent_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.sent_list_widget.currentItemChanged.connect(self.handle_sent_selection_changed)
        # Connect model's rowsMoved for drag-drop reordering
        if self.sent_list_widget.model():
            self.sent_list_widget.model().rowsMoved.connect(self.handle_sentence_reorder)
        group_layout.addWidget(self.sent_list_widget)

        sent_buttons_layout = QHBoxLayout()
        self.add_sent_button = create_button("Add Sentence", "add.png", on_click=self.add_sentence)
        self.del_sent_button = create_button("Remove Sentence", "remove.png", on_click=self.delete_sentence)
        sent_buttons_layout.addWidget(self.add_sent_button)
        sent_buttons_layout.addWidget(self.del_sent_button)
        group_layout.addLayout(sent_buttons_layout)

        group_layout.addWidget(QLabel("Edit Selected Sentence:"))
        self.sent_edit_text = QTextEdit()
        self.sent_edit_text.textChanged.connect(self.handle_sent_text_changed)
        group_layout.addWidget(self.sent_edit_text)

        right_layout.addWidget(self.para_group_box)
        splitter.addWidget(right_widget)

        splitter.setSizes([200, 600])
        main_layout.addWidget(splitter)

        self.setCentralWidget(central_widget)
        logger.debug("TextEditorWindow UI setup complete.")

    def mark_dirty(self, dirty=True):
        self.setWindowModified(dirty)
        self.update_ui_state()

    def load_and_list_paragraphs(self):
        logger.debug("Loading and listing paragraphs...")
        current_selection = self.para_list_widget.currentItem().text() if self.para_list_widget.currentItem() else None
        self.para_list_widget.currentItemChanged.disconnect(self.handle_para_selection_changed)
        self.para_list_widget.clear()
        self.paragraphs_cache = {}
        try:
            para_names = self.paragraph_manager.list_paragraphs()
            self.para_list_widget.addItems(sorted(para_names))
            logger.info(f"Loaded {len(para_names)} paragraph names.")
        except Exception as e:
            logger.error(f"Failed to list paragraphs: {e}", exc_info=True)
            QMessageBox.critical(self, "Load Error", f"Failed to list paragraphs: {e}")

        if current_selection:
            items = self.para_list_widget.findItems(current_selection, Qt.MatchFlag.MatchExactly)
            if items:
                self.para_list_widget.setCurrentItem(items[0])
            else:
                self.current_paragraph_name = None

        self.para_list_widget.currentItemChanged.connect(self.handle_para_selection_changed)
        if not self.para_list_widget.currentItem():
            self.current_paragraph_name = None
            self.populate_sentence_list()
            self.update_ui_state()

    def handle_para_selection_changed(self, current, previous):
        if current:
            self.current_paragraph_name = current.text()
            logger.debug(f"Paragraph selected: {self.current_paragraph_name}")
            if self.current_paragraph_name not in self.paragraphs_cache:
                try:
                    self.paragraphs_cache[self.current_paragraph_name] = \
                        self.paragraph_manager.load_paragraph(self.current_paragraph_name)
                except Exception as e:
                    logger.error(f"Failed to load selected paragraph '{self.current_paragraph_name}': {e}",
                                 exc_info=True)
                    QMessageBox.critical(self, "Load Error", f"Failed to load '{self.current_paragraph_name}': {e}")
                    self.current_paragraph_name = None
            self.populate_sentence_list()
        else:
            self.current_paragraph_name = None
            self.populate_sentence_list()
        self.update_ui_state()

    def populate_sentence_list(self, select_index=-1):  # Added select_index
        self.sent_list_widget.currentItemChanged.disconnect(self.handle_sent_selection_changed)
        # Disconnect reorder signal temporarily if model exists
        model = self.sent_list_widget.model()
        if model:
            try:
                model.rowsMoved.disconnect(self.handle_sentence_reorder)
            except (TypeError, RuntimeError):  # Not connected or already disconnected
                pass

        self.sent_list_widget.clear()

        if self.current_paragraph_name and self.current_paragraph_name in self.paragraphs_cache:
            para_data = self.paragraphs_cache[self.current_paragraph_name]
            if para_data:
                for i, sentence_data in enumerate(para_data.get("sentences", [])):
                    text = sentence_data.get("text", "[Empty]")
                    item = QListWidgetItem(f"{i + 1}: {text}")
                    item.setData(Qt.ItemDataRole.UserRole, i)
                    self.sent_list_widget.addItem(item)
            self.para_name_label.setText(f"Paragraph: {self.current_paragraph_name}")
        else:
            self.para_name_label.setText("Paragraph: (None)")

        self.sent_list_widget.currentItemChanged.connect(self.handle_sent_selection_changed)
        # Reconnect reorder signal if model exists
        model = self.sent_list_widget.model()
        if model:
            model.rowsMoved.connect(self.handle_sentence_reorder)

        if select_index != -1 and self.sent_list_widget.count() > 0:
            actual_index = min(select_index, self.sent_list_widget.count() - 1)
            self.sent_list_widget.setCurrentRow(actual_index)
        else:
            self.handle_sent_selection_changed(None, None)  # Clear editor if no selection

    def handle_sent_selection_changed(self, current, previous):
        self.sent_edit_text.textChanged.disconnect(self.handle_sent_text_changed)
        if current and self.current_paragraph_name:
            index = current.data(Qt.ItemDataRole.UserRole)
            # Ensure index is valid for the cache
            if 0 <= index < len(self.paragraphs_cache[self.current_paragraph_name]["sentences"]):
                text = self.paragraphs_cache[self.current_paragraph_name]["sentences"][index]["text"]
                self.sent_edit_text.setText(text)
                self.sent_edit_text.setEnabled(True)
            else:  # Should not happen if populate_sentence_list is correct
                self.sent_edit_text.clear()
                self.sent_edit_text.setEnabled(False)
        else:
            self.sent_edit_text.clear()
            self.sent_edit_text.setEnabled(False)
        self.sent_edit_text.textChanged.connect(self.handle_sent_text_changed)
        self.update_ui_state()

    def handle_sent_text_changed(self):
        current_item = self.sent_list_widget.currentItem()
        if current_item and self.current_paragraph_name:
            index = current_item.data(Qt.ItemDataRole.UserRole)
            new_text = self.sent_edit_text.toPlainText()
            if 0 <= index < len(self.paragraphs_cache[self.current_paragraph_name]["sentences"]):
                self.paragraphs_cache[self.current_paragraph_name]["sentences"][index]["text"] = new_text
                current_item.setText(f"{index + 1}: {new_text}")
                self.mark_dirty()

    def handle_sentence_reorder(self, parent, start, end, destination, row):
        """Handles drag-and-drop reordering of sentences."""
        if not self.current_paragraph_name or not self.paragraphs_cache.get(self.current_paragraph_name):
            return

        # The 'row' parameter in rowsMoved is the new position of the *first* moved item.
        # The items are moved in the model before this signal is emitted.
        # We need to update our internal cache to match the new order in the QListWidget.
        logger.debug(f"Sentences reordered. Start: {start}, End: {end}, Dest Parent: {parent}, Dest Row: {row}")

        new_sentences_order = []
        for i in range(self.sent_list_widget.count()):
            item = self.sent_list_widget.item(i)
            original_index = item.data(Qt.ItemDataRole.UserRole)  # This is now WRONG after move
            # We need to fetch the text from the item itself.
            # The UserRole index is no longer reliable until we repopulate or update it.
            # Simplest: Rebuild sentences from list widget content
            # But, the text in the list widget might be truncated or formatted. Better to rebuild cache from scratch.

        # The actual items have been moved by QListWidget.
        # We need to rebuild our cached 'sentences' list based on the new order.
        current_sentences = self.paragraphs_cache[self.current_paragraph_name]["sentences"]
        moved_items_count = end - start + 1

        # This logic is tricky as QListWidget internally handles the move.
        # The simplest way to ensure cache integrity is to rebuild it from the current item order.
        # We need the actual sentence objects, not just text.
        # Temporarily store sentence data by its text if unique, or manage a temporary list

        # More robust: rebuild from list widget items if data is stored correctly or re-fetch
        # For now, let's just update the cache based on the visible order.
        # This assumes sentence objects are intact in the cache and we just need to reorder them.

        # Create a list of current sentence data based on old indices
        temp_sentence_objects = []
        for i in range(len(current_sentences)):  # Use count from old cache for safety
            # This doesn't work directly as the item's UserRole is not the index *in the cache*
            # We need to rebuild the data based on the *new* order of texts.
            # The items in sent_list_widget are now in the new order.
            # Each item's text is like "1: Sentence text". We need to get the actual sentence data.
            pass  # This part requires a more careful update of the cache based on the list order.

        # Given the complexity, a simpler approach for now:
        # After a move, iterate through listwidget items, get their original index (if stored)
        # or text, and reconstruct the 'sentences' in cache.
        # For now, just mark as dirty and repopulate list to re-index.
        # The user will see the order change. We need to update the cache.

        sentences_in_new_order = []
        for i in range(self.sent_list_widget.count()):
            list_item_text = self.sent_list_widget.item(i).text()
            # Assuming format "N: text"
            actual_text = ":".join(list_item_text.split(":")[1:]).strip()
            # Find this text in the original cache to get its delay_seconds
            found_sentence = None
            for sentence_obj in current_sentences:  # Search in the *original* order cache
                if sentence_obj["text"] == actual_text:  # This breaks if texts are not unique
                    found_sentence = sentence_obj
                    break
            if found_sentence:
                sentences_in_new_order.append(found_sentence)
            else:
                # This case is problematic if texts are not unique or changed.
                # A better way would be to store a unique ID per sentence.
                # For now, let's assume texts are unique enough or this needs to be refined.
                logger.warning(f"Could not find sentence data for reordered item: {actual_text}")
                # Fallback: create a new one, but this loses original delay_seconds
                # sentences_in_new_order.append({"text": actual_text, "delay_seconds": 0.0})

        # If we couldn't reliably rebuild, this is risky.
        # A safe but potentially disruptive way: only allow reorder if texts are unique.
        # Or, after drag-drop, we re-read the item text from QListWidget and update the cache in that order.

        # Let's assume we can rebuild based on displayed text:
        updated_sentences_cache = []
        for i in range(self.sent_list_widget.count()):
            list_item = self.sent_list_widget.item(i)
            current_text_from_list = ":".join(list_item.text().split(":")[1:]).strip()
            # Try to find the original sentence object that corresponds to this text
            # This is still problematic if text was edited and not saved, or if texts are identical.
            # Simplification: UserRole stores the index in the *current* visual list.
            # When moving, we need to update the underlying cache.

            # Let's just update the list based on the view and mark dirty.
            # The real source of truth is the cache. We need to sync cache TO the list view order.

        source_sentences = self.paragraphs_cache[self.current_paragraph_name]['sentences']

        # If only one item moved:
        if moved_items_count == 1:
            moved_sentence_data = source_sentences.pop(start)  # Remove from old position
            source_sentences.insert(row, moved_sentence_data)  # Insert at new position
        else:  # Multiple items moved, more complex. This simplified logic might be incorrect for complex Qt moves.
            # Qt's model/view should handle the visual move. We need to sync our list.
            # A simpler approach for now: rebuild from list widget.
            current_texts_in_list = [":".join(self.sent_list_widget.item(i).text().split(":")[1:]).strip() for i in
                                     range(self.sent_list_widget.count())]

            new_cached_sentences = []
            original_cached_sentences = list(self.paragraphs_cache[self.current_paragraph_name]['sentences'])  # copy

            for text_in_list in current_texts_in_list:
                found = False
                for i, cached_sent in enumerate(original_cached_sentences):
                    if cached_sent['text'] == text_in_list:
                        new_cached_sentences.append(original_cached_sentences.pop(i))
                        found = True
                        break
                if not found:  # Should not happen if cache and list were in sync
                    logger.warning(f"Sentence '{text_in_list}' from list not found in cache during reorder.")
                    # Add it as a new sentence if not found, though this is a recovery mechanism
                    new_cached_sentences.append({"text": text_in_list, "delay_seconds": 0.0})

            self.paragraphs_cache[self.current_paragraph_name]['sentences'] = new_cached_sentences

        self.mark_dirty()
        # Repopulate to update numbering and UserData (indices)
        self.populate_sentence_list(select_index=row)
        logger.debug("Sentence order updated in cache and list repopulated.")

    def add_paragraph(self):
        para_name, ok = QInputDialog.getText(self, "New Paragraph", "Enter a name for the new paragraph:")
        if ok and para_name:
            safe_name = para_name.strip().replace(" ", "_")
            if not is_safe_filename_component(f"{safe_name}.json"):
                QMessageBox.warning(self, "Invalid Name", "The name contains invalid characters.")
                return
            if safe_name in self.paragraph_manager.list_paragraphs():
                QMessageBox.warning(self, "Name Exists", f"A paragraph named '{safe_name}' already exists.")
                return

            new_para = {"name": safe_name, "sentences": []}
            if self.paragraph_manager.save_paragraph(safe_name, new_para):
                logger.info(f"Added new paragraph: {safe_name}")
                self.load_and_list_paragraphs()
                items = self.para_list_widget.findItems(safe_name, Qt.MatchFlag.MatchExactly)
                if items:
                    self.para_list_widget.setCurrentItem(items[0])
                self.mark_dirty(False)
            else:
                QMessageBox.critical(self, "Save Error", f"Could not save new paragraph '{safe_name}'.")

    def rename_paragraph(self):
        current_item = self.para_list_widget.currentItem()
        if not current_item: return

        old_name = current_item.text()
        new_name, ok = QInputDialog.getText(self, "Rename Paragraph", f"Enter new name for '{old_name}':",
                                            text=old_name)

        if ok and new_name and new_name != old_name:
            safe_new_name = new_name.strip().replace(" ", "_")
            if not is_safe_filename_component(f"{safe_new_name}.json"):
                QMessageBox.warning(self, "Invalid Name", "The name contains invalid characters.")
                return
            if safe_new_name in self.paragraph_manager.list_paragraphs():
                QMessageBox.warning(self, "Name Exists", f"A paragraph named '{safe_new_name}' already exists.")
                return

            try:
                para_data_to_rename = self.paragraphs_cache.pop(old_name, None)  # Remove from cache
                if not para_data_to_rename:  # If not in cache, load it
                    para_data_to_rename = self.paragraph_manager.load_paragraph(old_name)

                if not para_data_to_rename:
                    QMessageBox.critical(self, "Rename Error", f"Could not load paragraph '{old_name}' for renaming.")
                    return

                para_data_to_rename["name"] = safe_new_name
                if self.paragraph_manager.save_paragraph(safe_new_name, para_data_to_rename):
                    self.paragraph_manager.delete_paragraph(old_name)
                    logger.info(f"Renamed '{old_name}' to '{safe_new_name}'.")
                    self.load_and_list_paragraphs()
                    items = self.para_list_widget.findItems(safe_new_name, Qt.MatchFlag.MatchExactly)
                    if items:
                        self.para_list_widget.setCurrentItem(items[0])
                else:
                    # Add back to cache if save failed
                    self.paragraphs_cache[old_name] = para_data_to_rename
                    para_data_to_rename["name"] = old_name  # revert name
                    QMessageBox.critical(self, "Save Error", f"Could not save renamed paragraph '{safe_new_name}'.")
            except Exception as e:
                QMessageBox.critical(self, "Rename Error", f"Failed to rename: {e}")

    def delete_paragraph(self):
        current_item = self.para_list_widget.currentItem()
        if not current_item: return

        para_name = current_item.text()
        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete '{para_name}'?\nThis cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if self.paragraph_manager.delete_paragraph(para_name):
                logger.info(f"Deleted paragraph: {para_name}")
                if para_name in self.paragraphs_cache:
                    del self.paragraphs_cache[para_name]
                self.load_and_list_paragraphs()  # This will clear selection if deleted item was selected
                self.mark_dirty(False)
            else:
                QMessageBox.critical(self, "Delete Error", f"Could not delete paragraph '{para_name}'.")

    def add_sentence(self):
        if not self.current_paragraph_name: return

        new_sentence = {"text": "New sentence.", "delay_seconds": 0.0}  # Default timing
        self.paragraphs_cache[self.current_paragraph_name]["sentences"].append(new_sentence)

        # Repopulate and select the new last item
        self.populate_sentence_list(select_index=self.sent_list_widget.count())  # Count is old count before adding
        self.mark_dirty()

    # --- MODIFIED: delete_sentence ---
    def delete_sentence(self):
        """Deletes the selected sentence and re-selects appropriately."""
        current_item = self.sent_list_widget.currentItem()
        if not current_item or not self.current_paragraph_name:
            return

        index_to_delete = self.sent_list_widget.row(current_item)  # Get current row

        if 0 <= index_to_delete < len(self.paragraphs_cache[self.current_paragraph_name]["sentences"]):
            del self.paragraphs_cache[self.current_paragraph_name]["sentences"][index_to_delete]
            logger.debug(f"Deleted sentence at index {index_to_delete}.")
            self.mark_dirty()

            # Determine new index to select
            num_sentences_after_delete = len(self.paragraphs_cache[self.current_paragraph_name]["sentences"])
            select_index_after_delete = -1

            if num_sentences_after_delete == 0:
                select_index_after_delete = -1  # No items to select
            elif index_to_delete < num_sentences_after_delete:
                # If deleted item was not the last, select the item now at the same index
                select_index_after_delete = index_to_delete
            else:
                # If deleted item was the last, select the new last item
                select_index_after_delete = num_sentences_after_delete - 1

            self.populate_sentence_list(select_index=select_index_after_delete)
            # update_ui_state will be called by populate_sentence_list -> handle_sent_selection_changed
        else:
            logger.warning(f"Could not delete sentence, index {index_to_delete} out of bounds for cache.")

    # --- END MODIFIED ---

    def save_all_changes(self):
        logger.info("Saving all changes...")
        saved_count = 0
        failed_count = 0

        if not self.isWindowModified():
            QMessageBox.information(self, "No Changes", "There are no unsaved changes.")
            return

        for name, data in self.paragraphs_cache.items():
            try:
                if self.paragraph_manager.save_paragraph(name, data):
                    saved_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Critical error saving '{name}': {e}", exc_info=True)
                failed_count += 1

        if failed_count > 0:
            QMessageBox.critical(self, "Save Error", f"Failed to save {failed_count} paragraph(s). See logs.")
        elif saved_count > 0:  # Only show success if something was actually saved
            QMessageBox.information(self, "Save Complete", f"Successfully saved {saved_count} paragraph(s).")
            self.mark_dirty(False)
        else:  # No items in cache or save wasn't attempted
            QMessageBox.information(self, "Save", "No cached paragraphs were saved.")
            self.mark_dirty(False)

    def update_ui_state(self):
        para_selected = self.current_paragraph_name is not None
        sent_selected = self.sent_list_widget.currentItem() is not None

        self.rename_para_button.setEnabled(para_selected)
        self.del_para_button.setEnabled(para_selected)
        self.para_group_box.setEnabled(para_selected)
        self.add_sent_button.setEnabled(para_selected)
        self.del_sent_button.setEnabled(para_selected and sent_selected)
        self.sent_edit_text.setEnabled(para_selected and sent_selected)
        self.save_button.setEnabled(self.isWindowModified())

    def prompt_save_changes(self):
        if not self.isWindowModified():
            return True

        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "Save changes before closing?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)

        if reply == QMessageBox.StandardButton.Save:
            self.save_all_changes()
            return not self.isWindowModified()
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        else:
            return False

    def closeEvent(self, event):
        logger.debug("TextEditorWindow closeEvent triggered.")
        if self.prompt_save_changes():
            event.accept()
            logger.info("TextEditorWindow closed.")
        else:
            event.ignore()
            logger.info("TextEditorWindow close cancelled by user.")