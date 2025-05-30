# myapp/gui/sentence_manager.py
import logging
from PySide6.QtWidgets import (
    QTableWidgetItem, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QTextCursor

logger = logging.getLogger(__name__)

class SentenceManager(QObject):
    """
    Manages sentences for the currently selected paragraph,
    including interactions with the sentence table and editor.
    """
    sentences_updated = Signal()  # Emitted when sentences change, prompting a dirty state

    def __init__(self, text_editor_window, sent_table_widget, sent_edit_text):
        super().__init__()
        self.editor_window = text_editor_window  # Reference to the main window
        self.sent_table_widget = sent_table_widget
        self.sent_edit_text = sent_edit_text

        self.current_paragraph_name = None
        self.current_paragraph_data = None
        self._block_signals = False

        # Connect signals for table and editor
        self.sent_table_widget.itemSelectionChanged.connect(self.handle_sent_selection_changed)
        self.sent_table_widget.itemChanged.connect(self.handle_sent_text_changed_from_table)
        self.sent_table_widget.verticalHeader().sectionMoved.connect(self.handle_sentence_reorder)
        self.sent_edit_text.textChanged.connect(self.handle_sent_editor_text_changed)

    def set_current_paragraph(self, paragraph_name, paragraph_data):
        """Sets the current paragraph to manage."""
        self.current_paragraph_name = paragraph_name
        self.current_paragraph_data = paragraph_data
        self.populate_sentence_table()
        self._update_editor_state_for_selection()

    def _get_sentences_list(self):
        """Safely gets the sentences list from the current paragraph data."""
        if self.current_paragraph_data:
            return self.current_paragraph_data.setdefault("sentences", [])
        return []

    def populate_sentence_table(self, select_row=-1):
        """Populates the sentence table with data from the current paragraph."""
        self._block_signals = True
        self.sent_table_widget.clearContents()
        self.sent_table_widget.setRowCount(0)

        if self.current_paragraph_data:
            sentences = self._get_sentences_list()
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
            self.sent_table_widget.resizeRowsToContents()

        self._block_signals = False
        if select_row != -1 and self.sent_table_widget.rowCount() > 0:
            actual_row = min(select_row, self.sent_table_widget.rowCount() - 1)
            self.sent_table_widget.selectRow(actual_row)
        else:
            self._update_editor_state_for_selection() # Ensure editor is updated based on (no)selection

    def handle_delay_changed(self, value):
        """Handles changes to a sentence's delay via the spinbox."""
        if self._block_signals or not self.current_paragraph_data:
            return
        sender = self.sender()
        if sender:
            row = sender.property("row")
            sentences = self._get_sentences_list()
            if row is not None and 0 <= row < len(sentences):
                sentences[row]["delay_seconds"] = value
                self.sentences_updated.emit()

    def _update_editor_state_for_selection(self):
        """Updates the QTextEdit based on the current table selection."""
        if self._block_signals: return # Prevent recursive updates
        self._block_signals = True

        selected_items = self.sent_table_widget.selectedItems()
        sentences = self._get_sentences_list()
        if selected_items and self.current_paragraph_data:
            row = self.sent_table_widget.row(selected_items[0])
            if 0 <= row < len(sentences):
                text = sentences[row].get("text", "")
                self.sent_edit_text.setText(text)
                self.sent_edit_text.setEnabled(True)
            else:
                self.sent_edit_text.clear()
                self.sent_edit_text.setEnabled(False)
        else:
            self.sent_edit_text.clear()
            self.sent_edit_text.setEnabled(False)
        self._block_signals = False

    def handle_sent_selection_changed(self):
        """Handles selection changes in the sentence table."""
        self._update_editor_state_for_selection()
        self.editor_window.update_ui_state() # Notify main window to update global UI state

    def handle_sent_text_changed_from_table(self, item):
        """Handles text changes directly in the QTableWidget cell."""
        if self._block_signals or not self.current_paragraph_data:
            return
        row = item.row()
        new_text = item.text()
        sentences = self._get_sentences_list()
        if 0 <= row < len(sentences):
            sentences[row]["text"] = new_text
            self._block_signals = True # Prevent feedback loop
            if self.sent_table_widget.currentRow() == row:
                self.sent_edit_text.setText(new_text) # Sync editor if it's the same sentence
            self._block_signals = False
            self.sentences_updated.emit()

    def handle_sent_editor_text_changed(self):
        """Handles text changes in the QTextEdit."""
        if self._block_signals or not self.current_paragraph_data:
            return

        current_row = self.sent_table_widget.currentRow()
        if current_row == -1: return

        new_text = self.sent_edit_text.toPlainText()
        sentences = self._get_sentences_list()

        if 0 <= current_row < len(sentences):
            sentences[current_row]["text"] = new_text
            self._block_signals = True # Prevent feedback loop
            table_item = self.sent_table_widget.item(current_row, 0)
            if table_item:
                table_item.setText(new_text)
            else:
                self.sent_table_widget.setItem(current_row, 0, QTableWidgetItem(new_text))
            self._block_signals = False
            self.sentences_updated.emit()

    def handle_sentence_reorder(self, logical_index_moved_from, old_visual_index, new_visual_index):
        """Handles reordering of sentences in the table."""
        if not self.current_paragraph_data or self._block_signals or old_visual_index == new_visual_index:
            return
        logger.debug(f"Row moved from visual index {old_visual_index} to {new_visual_index}")

        self._block_signals = True
        sentences_list = self._get_sentences_list()
        moved_sentence = sentences_list.pop(old_visual_index)
        sentences_list.insert(new_visual_index, moved_sentence)
        self._block_signals = False

        self.sentences_updated.emit()
        self.populate_sentence_table(select_row=new_visual_index)

    def add_sentence(self):
        """Adds a new sentence to the current paragraph."""
        if not self.current_paragraph_data: return
        new_sentence = {"text": "New sentence.", "delay_seconds": 2.0}

        current_row = self.sent_table_widget.currentRow()
        sentences_list = self._get_sentences_list()
        insert_index = current_row + 1 if current_row != -1 else len(sentences_list)

        sentences_list.insert(insert_index, new_sentence)
        self.populate_sentence_table(select_row=insert_index)
        self.sentences_updated.emit()

    def delete_sentence(self):
        """Deletes the selected sentence."""
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return

        sentences_list = self._get_sentences_list()
        if not (0 <= current_row < len(sentences_list)): return

        del sentences_list[current_row]

        new_row_count = len(sentences_list)
        select_index = min(current_row, new_row_count - 1) if new_row_count > 0 else -1

        self.populate_sentence_table(select_row=select_index)
        self.sentences_updated.emit()

    def split_sentence(self):
        """Splits the selected sentence at the cursor position in the editor."""
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return

        cursor = self.sent_edit_text.textCursor()
        pos = cursor.position()
        text = self.sent_edit_text.toPlainText()

        if 0 < pos < len(text):
            text1 = text[:pos].strip()
            text2 = text[pos:].strip()

            if not text1 or not text2:
                QMessageBox.warning(self.editor_window, "Split Error",
                                    "Cannot split into an empty sentence. Ensure cursor is not next to spaces that result in an empty part.")
                return

            sentences_list = self._get_sentences_list()
            if not (0 <= current_row < len(sentences_list)): return

            current_sentence_obj = sentences_list[current_row]
            current_delay = current_sentence_obj.get("delay_seconds", 2.0)
            current_sentence_obj["text"] = text1

            new_sentence_data = {"text": text2, "delay_seconds": current_delay}
            insert_index = current_row + 1
            sentences_list.insert(insert_index, new_sentence_data)

            self.populate_sentence_table(select_row=insert_index)
            self.sentences_updated.emit()
        else:
            QMessageBox.information(self.editor_window, "Split Info",
                                    "Place cursor within the text (not at the very start or end) to split.")

    def join_sentence(self):
        """Joins the selected sentence with the next one."""
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data:
            logger.debug("Join sentence: No row selected or no paragraph.")
            return

        sentences_list = self._get_sentences_list()
        if not (0 <= current_row < len(sentences_list) - 1):
            logger.debug("Join sentence: Selected sentence is the last one or invalid.")
            QMessageBox.information(self.editor_window, "Join Info",
                                    "Select a sentence that is not the last one to join it with the next.")
            return

        sentence1_obj = sentences_list[current_row]
        sentence2_obj = sentences_list[current_row + 1]
        text1 = sentence1_obj.get("text", "").strip()
        text2 = sentence2_obj.get("text", "").strip()

        joined_text = f"{text1} {text2}".strip() if text1 and text2 else (text1 or text2)
        sentence1_obj["text"] = joined_text
        del sentences_list[current_row + 1]

        logger.info(f"Joined sentence at row {current_row} with row {current_row + 1}.")
        self.populate_sentence_table(select_row=current_row)
        self.sentences_updated.emit()

    def get_current_sentence_count(self):
        return len(self._get_sentences_list())

    def get_selected_row(self):
        return self.sent_table_widget.currentRow()