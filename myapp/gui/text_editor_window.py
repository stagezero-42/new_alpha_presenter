# myapp/gui/text_editor_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QMessageBox, QInputDialog,
    QListWidgetItem, QAbstractItemView, QSplitter, QLabel,
    QGroupBox, QFormLayout, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QTextCursor  # Added QTextCursor

from ..text.paragraph_manager import ParagraphManager
from ..utils.paths import get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component

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
        self._block_signals = False

        try:
            icon_path = get_icon_file_path("text.png")
            if not icon_path or not os.path.exists(icon_path):
                icon_path = get_icon_file_path("edit.png")
            if icon_path and os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
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
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Paragraphs:"))
        self.para_list_widget = QListWidget()
        self.para_list_widget.currentItemChanged.connect(self.handle_para_selection_changed)
        left_layout.addWidget(self.para_list_widget)
        para_buttons_layout = QHBoxLayout()
        self.add_para_button = create_button("Add", "add.png", "Add New Paragraph", self.add_paragraph)
        self.rename_para_button = create_button("Rename", "edit.png", "Rename", self.rename_paragraph)
        self.del_para_button = create_button("Delete", "remove.png", "Delete", self.delete_paragraph)
        para_buttons_layout.addWidget(self.add_para_button)
        para_buttons_layout.addWidget(self.rename_para_button)
        para_buttons_layout.addWidget(self.del_para_button)
        left_layout.addLayout(para_buttons_layout)
        splitter.addWidget(left_widget)

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
        self.sent_table_widget.verticalHeader().sectionMoved.connect(self.handle_sentence_reorder)
        self.sent_table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sent_table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sent_table_widget.itemSelectionChanged.connect(self.handle_sent_selection_changed)
        self.sent_table_widget.itemChanged.connect(self.handle_sent_text_changed)
        group_layout.addWidget(self.sent_table_widget)

        sent_buttons_layout = QHBoxLayout()
        self.add_sent_button = create_button("Add", "add.png", "Add Sentence", self.add_sentence)
        self.del_sent_button = create_button("Remove", "remove.png", "Remove Selected Sentence", self.delete_sentence)
        self.split_sent_button = create_button("Split", "split.png", "Split Sentence at Cursor", self.split_sentence)
        sent_buttons_layout.addWidget(self.add_sent_button)
        sent_buttons_layout.addWidget(self.del_sent_button)
        sent_buttons_layout.addStretch()
        sent_buttons_layout.addWidget(self.split_sent_button)
        group_layout.addLayout(sent_buttons_layout)

        group_layout.addWidget(QLabel("Edit Selected Sentence Text:"))
        self.sent_edit_text = QTextEdit()
        self.sent_edit_text.textChanged.connect(self.handle_sent_editor_changed)
        group_layout.addWidget(self.sent_edit_text)

        right_layout.addWidget(self.para_group_box)
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 650])
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
        except Exception as e:
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
            self.populate_sentence_table()
        self.update_ui_state()

    def handle_para_selection_changed(self, current, previous):
        if current:
            self.current_paragraph_name = current.text()
            if self.current_paragraph_name not in self.paragraphs_cache:
                try:
                    self.paragraphs_cache[self.current_paragraph_name] = \
                        self.paragraph_manager.load_paragraph(self.current_paragraph_name)
                except Exception as e:
                    QMessageBox.critical(self, "Load Error", f"Failed to load '{self.current_paragraph_name}': {e}")
                    self.current_paragraph_name = None
            self.populate_sentence_table()
        else:
            self.current_paragraph_name = None
            self.populate_sentence_table()
        self.update_ui_state()

    def populate_sentence_table(self, select_row=-1):
        self._block_signals = True
        self.sent_table_widget.clearContents()
        self.sent_table_widget.setRowCount(0)

        if self.current_paragraph_name and self.current_paragraph_name in self.paragraphs_cache:
            para_data = self.paragraphs_cache[self.current_paragraph_name]
            if para_data:
                sentences = para_data.get("sentences", [])
                self.sent_table_widget.setRowCount(len(sentences))
                for i, sentence_data in enumerate(sentences):
                    text = sentence_data.get("text", "[Empty]")
                    delay = sentence_data.get("delay_seconds", 2.0)

                    text_item = QTableWidgetItem(text)
                    self.sent_table_widget.setItem(i, 0, text_item)

                    spin_box = QDoubleSpinBox()
                    spin_box.setMinimum(0.0)
                    spin_box.setMaximum(600.0)
                    spin_box.setSingleStep(0.1)
                    spin_box.setValue(delay)
                    spin_box.setSuffix(" s")
                    spin_box.setProperty("row", i)
                    spin_box.valueChanged.connect(self.handle_delay_changed)
                    self.sent_table_widget.setCellWidget(i, 1, spin_box)

            self.para_name_label.setText(f"Paragraph: {self.current_paragraph_name}")
            self.sent_table_widget.resizeRowsToContents()
        else:
            self.para_name_label.setText("Paragraph: (None)")

        self._block_signals = False
        if select_row != -1 and self.sent_table_widget.rowCount() > 0:
            actual_row = min(select_row, self.sent_table_widget.rowCount() - 1)
            self.sent_table_widget.selectRow(actual_row)
        else:
            self.handle_sent_selection_changed()

    def handle_delay_changed(self, value):
        if self._block_signals or not self.current_paragraph_name: return
        sender = self.sender()
        if sender:
            row = sender.property("row")
            if row is not None and 0 <= row < len(self.paragraphs_cache[self.current_paragraph_name]["sentences"]):
                self.paragraphs_cache[self.current_paragraph_name]["sentences"][row]["delay_seconds"] = value
                self.mark_dirty()

    def handle_sent_selection_changed(self):
        if self._block_signals: return
        self._block_signals = True
        selected_items = self.sent_table_widget.selectedItems()
        if selected_items and self.current_paragraph_name:
            row = self.sent_table_widget.row(selected_items[0])
            # Ensure row is valid for the cache, which might not be the case if table is empty
            if 0 <= row < len(self.paragraphs_cache[self.current_paragraph_name]["sentences"]):
                text = self.paragraphs_cache[self.current_paragraph_name]["sentences"][row]["text"]
                self.sent_edit_text.setText(text)
                self.sent_edit_text.setEnabled(True)
            else:  # Should not happen if populated correctly, but defensive
                self.sent_edit_text.clear()
                self.sent_edit_text.setEnabled(False)

        else:
            self.sent_edit_text.clear()
            self.sent_edit_text.setEnabled(False)
        self._block_signals = False
        self.update_ui_state()

    def handle_sent_text_changed(self, item):
        if self._block_signals or not self.current_paragraph_name: return
        row = item.row()
        new_text = item.text()
        # Ensure row is valid
        if 0 <= row < len(self.paragraphs_cache[self.current_paragraph_name]["sentences"]):
            self.paragraphs_cache[self.current_paragraph_name]["sentences"][row]["text"] = new_text
            self._block_signals = True
            if self.sent_table_widget.currentRow() == row:  # Only update editor if it's for the selected row
                self.sent_edit_text.setText(new_text)
            self._block_signals = False
            self.mark_dirty()

    def handle_sent_editor_changed(self):
        if self._block_signals or not self.current_paragraph_name: return
        selected_items = self.sent_table_widget.selectedItems()
        if not selected_items: return

        row = self.sent_table_widget.row(selected_items[0])
        new_text = self.sent_edit_text.toPlainText()

        if 0 <= row < len(self.paragraphs_cache[self.current_paragraph_name]["sentences"]):
            self.paragraphs_cache[self.current_paragraph_name]["sentences"][row]["text"] = new_text
            self._block_signals = True
            self.sent_table_widget.item(row, 0).setText(new_text)
            self._block_signals = False
            self.mark_dirty()

    def handle_sentence_reorder(self, logical_index, old_visual_index, new_visual_index):
        if not self.current_paragraph_name or self._block_signals: return  # Check block_signals
        logger.debug(f"Row moved from {old_visual_index} to {new_visual_index} (logical: {logical_index})")

        self._block_signals = True  # Block during manipulation
        moved_sentence = self.paragraphs_cache[self.current_paragraph_name]['sentences'].pop(old_visual_index)
        self.paragraphs_cache[self.current_paragraph_name]['sentences'].insert(new_visual_index, moved_sentence)
        self._block_signals = False

        self.mark_dirty()
        self.populate_sentence_table(select_row=new_visual_index)

    def add_sentence(self):
        if not self.current_paragraph_name: return
        new_sentence = {"text": "New sentence.", "delay_seconds": 2.0}

        current_row = self.sent_table_widget.currentRow()
        sentences_list = self.paragraphs_cache[self.current_paragraph_name]["sentences"]
        insert_index = current_row + 1 if current_row != -1 else len(sentences_list)

        sentences_list.insert(insert_index, new_sentence)
        self.populate_sentence_table(select_row=insert_index)
        self.mark_dirty()

    def delete_sentence(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_name: return

        sentences_list = self.paragraphs_cache[self.current_paragraph_name]["sentences"]
        del sentences_list[current_row]

        new_row_count = len(sentences_list)
        select_index = -1
        if new_row_count > 0:
            select_index = min(current_row, new_row_count - 1)

        self.populate_sentence_table(select_row=select_index)
        self.mark_dirty()

    def split_sentence(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_name: return

        cursor = self.sent_edit_text.textCursor()
        pos = cursor.position()
        text = self.sent_edit_text.toPlainText()

        if 0 < pos < len(text):
            text1 = text[:pos].strip()
            text2 = text[pos:].strip()

            if not text1 or not text2:
                QMessageBox.warning(self, "Split Error",
                                    "Cannot split into an empty sentence. Ensure cursor is not next to spaces that result in an empty part.")
                return

            # --- MODIFIED: Safe get for delay_seconds ---
            current_sentence_obj = self.paragraphs_cache[self.current_paragraph_name]["sentences"][current_row]
            current_delay = current_sentence_obj.get("delay_seconds", 2.0)
            # --- END MODIFIED ---

            current_sentence_obj["text"] = text1

            new_sentence_data = {"text": text2, "delay_seconds": current_delay}
            insert_index = current_row + 1
            self.paragraphs_cache[self.current_paragraph_name]["sentences"].insert(insert_index, new_sentence_data)

            self.populate_sentence_table(select_row=insert_index)
            self.mark_dirty()
        else:
            QMessageBox.information(self, "Split Info",
                                    "Place cursor within the text (not at the very start or end) to split.")

    def add_paragraph(self):
        para_name, ok = QInputDialog.getText(self, "New Paragraph", "Enter name:")
        if ok and para_name:
            safe_name = para_name.strip().replace(" ", "_")
            if not is_safe_filename_component(f"{safe_name}.json"):
                QMessageBox.warning(self, "Invalid Name", "Invalid characters.");
                return
            if safe_name in self.paragraph_manager.list_paragraphs():
                QMessageBox.warning(self, "Name Exists", "Name already exists.");
                return

            new_para = {"name": safe_name, "sentences": []}
            if self.paragraph_manager.save_paragraph(safe_name, new_para):
                self.load_and_list_paragraphs()
                items = self.para_list_widget.findItems(safe_name, Qt.MatchFlag.MatchExactly)
                if items: self.para_list_widget.setCurrentItem(items[0])
                self.mark_dirty(False)
            else:
                QMessageBox.critical(self, "Save Error", "Could not save.")

    def rename_paragraph(self):
        current_item = self.para_list_widget.currentItem()
        if not current_item: return
        old_name = current_item.text()
        new_name, ok = QInputDialog.getText(self, "Rename", f"New name for '{old_name}':", text=old_name)
        if ok and new_name and new_name != old_name:
            safe_new_name = new_name.strip().replace(" ", "_")
            if not is_safe_filename_component(f"{safe_new_name}.json"):
                QMessageBox.warning(self, "Invalid Name", "Invalid characters.");
                return
            if safe_new_name in self.paragraph_manager.list_paragraphs():
                QMessageBox.warning(self, "Name Exists", "Name already exists.");
                return

            try:
                para_data = self.paragraphs_cache.pop(old_name, None) or self.paragraph_manager.load_paragraph(old_name)
                if not para_data: QMessageBox.critical(self, "Rename Error", "Could not load."); return

                para_data["name"] = safe_new_name
                if self.paragraph_manager.save_paragraph(safe_new_name, para_data):
                    self.paragraph_manager.delete_paragraph(old_name)
                    self.load_and_list_paragraphs()
                    items = self.para_list_widget.findItems(safe_new_name, Qt.MatchFlag.MatchExactly)
                    if items: self.para_list_widget.setCurrentItem(items[0])
                else:
                    self.paragraphs_cache[old_name] = para_data
                    para_data["name"] = old_name
                    QMessageBox.critical(self, "Save Error", "Could not save.")
            except Exception as e:
                QMessageBox.critical(self, "Rename Error", f"Failed: {e}")

    def delete_paragraph(self):
        current_item = self.para_list_widget.currentItem()
        if not current_item: return
        para_name = current_item.text()
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete '{para_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.paragraph_manager.delete_paragraph(para_name):
                if para_name in self.paragraphs_cache: del self.paragraphs_cache[para_name]
                self.load_and_list_paragraphs();
                self.mark_dirty(False)
            else:
                QMessageBox.critical(self, "Delete Error", "Could not delete.")

    def save_all_changes(self):
        logger.info("Saving all changes...")
        saved_count = 0;
        failed_count = 0
        if not self.isWindowModified():
            QMessageBox.information(self, "No Changes", "No changes to save.");
            return

        self.update_cache_from_table()  # Ensure cache is up-to-date with table edits

        for name, data in self.paragraphs_cache.items():
            try:
                if self.paragraph_manager.save_paragraph(name, data):
                    saved_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error saving '{name}': {e}", exc_info=True);
                failed_count += 1

        if failed_count > 0:
            QMessageBox.critical(self, "Save Error", f"Failed to save {failed_count} file(s).")
        elif saved_count > 0:
            QMessageBox.information(self, "Save Complete", f"Saved {saved_count} file(s)."); self.mark_dirty(False)
        else:
            QMessageBox.information(self, "Save", "No files with changes to save."); self.mark_dirty(
                False)  # Changed message

    def update_cache_from_table(self):
        if not self.current_paragraph_name or not self.current_paragraph_name in self.paragraphs_cache: return

        # Only update if the paragraph data is actually loaded
        if not self.paragraphs_cache.get(self.current_paragraph_name):
            return

        new_sentences = []
        for row in range(self.sent_table_widget.rowCount()):
            text_item = self.sent_table_widget.item(row, 0)
            text = text_item.text() if text_item else ""

            spin_box_widget = self.sent_table_widget.cellWidget(row, 1)
            delay = spin_box_widget.value() if isinstance(spin_box_widget, QDoubleSpinBox) else 2.0
            new_sentences.append({"text": text, "delay_seconds": delay})

        self.paragraphs_cache[self.current_paragraph_name]['sentences'] = new_sentences
        logger.debug(f"Cache updated from table for '{self.current_paragraph_name}'.")

    def update_ui_state(self):
        para_selected = self.current_paragraph_name is not None
        sent_selected = self.sent_table_widget.currentRow() != -1

        self.rename_para_button.setEnabled(para_selected)
        self.del_para_button.setEnabled(para_selected)
        self.para_group_box.setEnabled(para_selected)
        self.add_sent_button.setEnabled(para_selected)
        self.del_sent_button.setEnabled(para_selected and sent_selected)
        self.split_sent_button.setEnabled(para_selected and sent_selected and self.sent_edit_text.isEnabled() and len(
            self.sent_edit_text.toPlainText()) > 0)  # Ensure text editor has content
        self.sent_edit_text.setEnabled(para_selected and sent_selected)
        self.save_button.setEnabled(self.isWindowModified())

    def prompt_save_changes(self):
        if not self.isWindowModified(): return True
        reply = QMessageBox.question(self, 'Unsaved Changes', "Save changes?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Save:
            self.save_all_changes();
            return not self.isWindowModified()
        return reply != QMessageBox.StandardButton.Cancel

    def closeEvent(self, event):
        if self.prompt_save_changes():
            event.accept()
        else:
            event.ignore()