# myapp/gui/sentence_manager.py
import logging
import copy
from PySide6.QtWidgets import (
    QTableWidgetItem, QDoubleSpinBox, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QTextCursor

from ..audio.audio_track_manager import AudioTrackManager
from ..utils.schemas import DEFAULT_VOICE_OVER_VOLUME
from .audio_import_dialog import AudioImportDialog # NEW

logger = logging.getLogger(__name__)


class SentenceManager(QObject):
    sentences_updated = Signal()
    voice_over_changed = Signal(str, float) # Emits track_name, volume
    selected_sentence_vo_track_for_player = Signal(str) # Emits track_name or None # NEW

    COL_TEXT = 0 # NEW
    COL_DELAY = 1 # NEW

    def __init__(self, text_editor_window, sent_table_widget, sent_edit_text, track_manager: AudioTrackManager):
        super().__init__()
        self.editor_window = text_editor_window
        self.sent_table_widget = sent_table_widget
        self.sent_edit_text = sent_edit_text
        self.track_manager = track_manager

        self.current_paragraph_name = None
        self.current_paragraph_data = None
        self._block_signals = False

        self.sent_table_widget.itemSelectionChanged.connect(self.handle_sent_selection_changed)
        self.sent_table_widget.itemChanged.connect(self.handle_sent_text_changed_from_table)
        self.sent_table_widget.verticalHeader().sectionMoved.connect(self.handle_sentence_reorder)
        self.sent_edit_text.textChanged.connect(self.handle_sent_editor_text_changed)

    def set_current_paragraph(self, paragraph_name, paragraph_data):
        self.current_paragraph_name = paragraph_name
        self.current_paragraph_data = paragraph_data
        self.populate_sentence_table()
        # If no sentence selected after populating (e.g., empty paragraph), emit signals to clear VO UI and player
        if self.sent_table_widget.currentRow() == -1:
            self.voice_over_changed.emit(None, DEFAULT_VOICE_OVER_VOLUME)
            self.selected_sentence_vo_track_for_player.emit(None)


    def _get_sentences_list(self):
        if self.current_paragraph_data:
            return self.current_paragraph_data.setdefault("sentences", [])
        return []

    def get_sentence_data(self, row_index: int) -> dict | None:
        sentences = self._get_sentences_list()
        if 0 <= row_index < len(sentences):
            return sentences[row_index]
        return None

    def populate_sentence_table(self, select_row=-1):
        self._block_signals = True
        self.sent_table_widget.clearContents()
        self.sent_table_widget.setRowCount(0)
        if self.current_paragraph_data:
            sentences = self._get_sentences_list()
            self.sent_table_widget.setRowCount(len(sentences))
            for i, sentence_data in enumerate(sentences):
                text = sentence_data.get("text", "[Empty]")
                sentence_data.setdefault("voice_over_track_name", None)
                sentence_data.setdefault("voice_over_volume", DEFAULT_VOICE_OVER_VOLUME)
                delay = sentence_data.get("delay_seconds", 0.1) # Ensure default for new sentences
                text_item = QTableWidgetItem(text)
                self.sent_table_widget.setItem(i, self.COL_TEXT, text_item) # Use COL_TEXT
                spin_box = QDoubleSpinBox()
                spin_box.setMinimum(0.0);
                spin_box.setMaximum(600.0)
                spin_box.setSingleStep(0.1);
                spin_box.setDecimals(1); # Show one decimal place
                spin_box.setValue(delay)
                spin_box.setSuffix(" s");
                spin_box.setProperty("row", i)
                spin_box.valueChanged.connect(self.handle_delay_changed)
                self.sent_table_widget.setCellWidget(i, self.COL_DELAY, spin_box) # Use COL_DELAY
            self.sent_table_widget.resizeRowsToContents()
        self._block_signals = False

        selected_row_after_populate = -1
        if select_row != -1 and 0 <= select_row < self.sent_table_widget.rowCount():
            self.sent_table_widget.selectRow(select_row)
            selected_row_after_populate = select_row
        elif self.sent_table_widget.rowCount() > 0:
            self.sent_table_widget.selectRow(0)
            selected_row_after_populate = 0

        # Ensure UI (including player) updates based on the new selection or lack thereof
        if selected_row_after_populate != -1:
            self._update_editor_state_for_selection() # This will emit necessary signals
        else: # No rows, clear everything
            self.sent_edit_text.clear()
            self.sent_edit_text.setEnabled(False)
            self.voice_over_changed.emit(None, DEFAULT_VOICE_OVER_VOLUME)
            self.selected_sentence_vo_track_for_player.emit(None)

        self.editor_window.update_ui_state()


    def handle_delay_changed(self, value):
        if self._block_signals or not self.current_paragraph_data: return
        sender = self.sender()
        if sender:
            row = sender.property("row")
            sentences = self._get_sentences_list()
            if row is not None and 0 <= row < len(sentences):
                # Round to one decimal place before comparing and saving
                rounded_value = round(value, 1)
                if sentences[row]["delay_seconds"] != rounded_value:
                    sentences[row]["delay_seconds"] = rounded_value
                    self.sentences_updated.emit()
                    # If this change was user-initiated, ensure the spinbox reflects the rounded value
                    # to avoid immediate re-trigger or visual discrepancy.
                    if sender.value() != rounded_value:
                        self._block_signals = True # Prevent re-triggering this handler
                        sender.setValue(rounded_value)
                        self._block_signals = False


    def _update_editor_state_for_selection(self):
        if self._block_signals: return
        self._block_signals = True
        selected_items = self.sent_table_widget.selectedItems()
        sentences = self._get_sentences_list()
        vo_track_name = None
        vo_volume = DEFAULT_VOICE_OVER_VOLUME

        if selected_items and self.current_paragraph_data:
            row = self.sent_table_widget.row(selected_items[0])
            if 0 <= row < len(sentences):
                sentence_data = sentences[row]
                text = sentence_data.get("text", "")
                self.sent_edit_text.setText(text)
                self.sent_edit_text.setEnabled(True)
                vo_track_name = sentence_data.get("voice_over_track_name")
                vo_volume = sentence_data.get("voice_over_volume", DEFAULT_VOICE_OVER_VOLUME)
            else: # Should not happen if row is valid index from selectedItems
                self.sent_edit_text.clear();
                self.sent_edit_text.setEnabled(False)
        else: # No item selected
            self.sent_edit_text.clear();
            self.sent_edit_text.setEnabled(False)

        self._block_signals = False
        self.voice_over_changed.emit(vo_track_name, vo_volume)
        self.selected_sentence_vo_track_for_player.emit(vo_track_name) # NEW: Emit for player


    def handle_sent_selection_changed(self):
        self._update_editor_state_for_selection()
        self.editor_window.update_ui_state()

    def handle_sent_text_changed_from_table(self, item):
        if self._block_signals or not self.current_paragraph_data or item.column() != self.COL_TEXT: return
        row = item.row();
        new_text = item.text()
        sentences = self._get_sentences_list()
        if 0 <= row < len(sentences):
            if sentences[row]["text"] != new_text:
                sentences[row]["text"] = new_text
                self._block_signals = True
                if self.sent_table_widget.currentRow() == row: self.sent_edit_text.setText(new_text)
                self._block_signals = False
                self.sentences_updated.emit()

    def handle_sent_editor_text_changed(self):
        if self._block_signals or not self.current_paragraph_data: return
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1: return
        new_text = self.sent_edit_text.toPlainText()
        sentences = self._get_sentences_list()
        if 0 <= current_row < len(sentences):
            if sentences[current_row]["text"] != new_text:
                sentences[current_row]["text"] = new_text
                self._block_signals = True
                table_item = self.sent_table_widget.item(current_row, self.COL_TEXT)
                if table_item:
                    table_item.setText(new_text)
                else: # Should not happen if row is valid
                    self.sent_table_widget.setItem(current_row, self.COL_TEXT, QTableWidgetItem(new_text))
                self._block_signals = False
                self.sentences_updated.emit()

    def handle_sentence_reorder(self, logical_old_index, old_visual_index, new_visual_index):
        if not self.current_paragraph_data or self._block_signals or old_visual_index == new_visual_index: return
        logger.debug(f"Row moved from visual index {old_visual_index} to {new_visual_index}")
        self._block_signals = True
        sentences_list = self._get_sentences_list()
        moved_sentence = sentences_list.pop(old_visual_index)
        sentences_list.insert(new_visual_index, moved_sentence)
        self._block_signals = False
        self.sentences_updated.emit()
        self.populate_sentence_table(select_row=new_visual_index)


    def add_sentence(self):
        if not self.current_paragraph_data: return
        new_sentence = {"text": "New sentence.", "delay_seconds": 2.0,
                        "voice_over_track_name": None, "voice_over_volume": DEFAULT_VOICE_OVER_VOLUME}
        current_row = self.sent_table_widget.currentRow()
        sentences_list = self._get_sentences_list()
        insert_index = current_row + 1 if current_row != -1 else len(sentences_list)
        sentences_list.insert(insert_index, new_sentence)
        self.populate_sentence_table(select_row=insert_index)
        self.sentences_updated.emit()


    def duplicate_sentence(self):
        if not self.current_paragraph_data: return
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1:
            QMessageBox.information(self.editor_window, "Duplicate Sentence", "Please select a sentence to duplicate.")
            return
        sentences_list = self._get_sentences_list()
        if not (0 <= current_row < len(sentences_list)): return

        original_sentence_data = sentences_list[current_row]
        duplicated_sentence_data = copy.deepcopy(original_sentence_data)
        insert_index = current_row + 1
        sentences_list.insert(insert_index, duplicated_sentence_data)
        logger.info(f"Duplicated sentence at row {current_row} to {insert_index}.")
        self.populate_sentence_table(select_row=insert_index)
        self.sentences_updated.emit()

    def insert_blank_sentence(self):
        if not self.current_paragraph_data: return
        blank_sentence = {"text": "", "delay_seconds": 0.1,
                          "voice_over_track_name": None, "voice_over_volume": DEFAULT_VOICE_OVER_VOLUME}
        current_row = self.sent_table_widget.currentRow()
        sentences_list = self._get_sentences_list()
        insert_index = current_row + 1 if current_row != -1 else len(sentences_list)
        sentences_list.insert(insert_index, blank_sentence)
        logger.info(f"Inserted blank sentence at index {insert_index}.")
        self.populate_sentence_table(select_row=insert_index)
        self.sentences_updated.emit()

    def delete_sentence(self):
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
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return

        cursor = self.sent_edit_text.textCursor();
        pos = cursor.position();
        text = self.sent_edit_text.toPlainText()

        if 0 < pos < len(text):
            text1 = text[:pos].strip();
            text2 = text[pos:].strip()
            if not text1 or not text2:
                QMessageBox.warning(self.editor_window, "Split Error", "Cannot split into an empty sentence."); return

            sentences_list = self._get_sentences_list()
            if not (0 <= current_row < len(sentences_list)): return

            current_sentence_obj = sentences_list[current_row]
            current_delay = current_sentence_obj.get("delay_seconds", 2.0)
            # Keep original VO for first part, new sentence gets no VO initially
            current_sentence_obj["text"] = text1
            new_sentence_data = {"text": text2, "delay_seconds": current_delay / 2,
                                 "voice_over_track_name": None, "voice_over_volume": DEFAULT_VOICE_OVER_VOLUME}
            current_sentence_obj["delay_seconds"] = current_delay / 2

            insert_index = current_row + 1
            sentences_list.insert(insert_index, new_sentence_data)
            self.populate_sentence_table(select_row=insert_index); # Select the new (second part) sentence
            self.sentences_updated.emit()
        else:
            QMessageBox.information(self.editor_window, "Split Info", "Place cursor within text to split.")


    def join_sentence(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return
        sentences_list = self._get_sentences_list()
        if not (0 <= current_row < len(sentences_list) - 1): # Can only join if not the last sentence
            QMessageBox.information(self.editor_window, "Join Info", "Select a sentence that is not the last one."); return

        s1 = sentences_list[current_row];
        s2 = sentences_list[current_row + 1]
        t1 = s1.get("text", "").strip();
        t2 = s2.get("text", "").strip()

        s1["text"] = f"{t1} {t2}".strip() if t1 and t2 else (t1 or t2)
        s1["delay_seconds"] = round(s1.get("delay_seconds", 0) + s2.get("delay_seconds", 0), 1)
        # Voice-over from s1 is kept, s2's VO is discarded. User must re-evaluate.

        del sentences_list[current_row + 1]
        self.populate_sentence_table(select_row=current_row);
        self.sentences_updated.emit()

    def _assign_track_to_sentence_internal(self, row: int, track_name: str):
        """Internal helper to assign a track and update UI."""
        sentences = self._get_sentences_list()
        if not (0 <= row < len(sentences)): return

        sentence_data = sentences[row]
        sentence_data["voice_over_track_name"] = track_name
        current_volume = sentence_data.get("voice_over_volume", DEFAULT_VOICE_OVER_VOLUME)
        sentence_data["voice_over_volume"] = current_volume # Ensure it exists

        self.populate_sentence_table(select_row=row) # Refresh table cell for delay
        self.voice_over_changed.emit(track_name, current_volume)
        self.selected_sentence_vo_track_for_player.emit(track_name) # NEW
        self.sentences_updated.emit()


    def assign_voice_over_track(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data:
            QMessageBox.warning(self.editor_window, "No Sentence", "Please select a sentence first.")
            return

        available_tracks = sorted(self.track_manager.list_audio_tracks())
        if not available_tracks:
            QMessageBox.information(self.editor_window, "No Audio Tracks",
                                    "No audio tracks found. Import audio first.")
            return

        track_name, ok = QInputDialog.getItem(self.editor_window, "Assign Voice-Over", "Select Audio Track:",
                                              available_tracks, 0, False)
        if ok and track_name:
            self._assign_track_to_sentence_internal(current_row, track_name)
            QMessageBox.information(self.editor_window, "Track Assigned",
                                   f"Track '{track_name}' assigned.\nUse the 'Set Sentence Duration from Player' button to update sentence duration if needed.")


    def import_and_assign_track_to_selected_sentence(self, parent_dialog):
        """Handles importing a new track and assigning it to the selected sentence."""
        selected_row = self.get_selected_row()
        if selected_row == -1:
            QMessageBox.warning(parent_dialog, "No Sentence", "Please select a sentence in the editor first.")
            return

        import_dialog = AudioImportDialog(parent_dialog, self.track_manager)
        if import_dialog.exec():
            newly_imported_track_name = import_dialog.get_imported_track_info()["track_name"]
            if newly_imported_track_name:
                logger.info(f"AudioImportDialog successful, new track: {newly_imported_track_name}. Assigning to sentence {selected_row}.")
                self._assign_track_to_sentence_internal(selected_row, newly_imported_track_name)
                QMessageBox.information(self.editor_window, "Track Imported & Assigned",
                                       f"Track '{newly_imported_track_name}' imported and assigned.\n"
                                       "Use 'Set Sentence Duration from Player' to update duration.")
            else:
                logger.warning("AudioImportDialog accepted, but no track info returned.")
        else:
            logger.info("AudioImportDialog cancelled or closed.")


    def set_sentence_delay_seconds(self, row_index: int, delay_seconds: float):
        """Sets the delay for a sentence and updates UI."""
        if not self.current_paragraph_data: return
        sentences = self._get_sentences_list()
        if 0 <= row_index < len(sentences):
            rounded_delay = round(delay_seconds, 1)
            if sentences[row_index]["delay_seconds"] != rounded_delay:
                sentences[row_index]["delay_seconds"] = rounded_delay
                self.sentences_updated.emit()
                # Update the spinbox in the table directly
                self._block_signals = True
                cell_widget = self.sent_table_widget.cellWidget(row_index, self.COL_DELAY)
                if isinstance(cell_widget, QDoubleSpinBox):
                    cell_widget.setValue(rounded_delay)
                self._block_signals = False
                logger.info(f"Delay for sentence {row_index} set to {rounded_delay}s.")
        else:
            logger.warning(f"Tried to set delay for invalid row index: {row_index}")


    def clear_voice_over_track(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return

        sentences = self._get_sentences_list()
        sentence_data = sentences[current_row]
        sentence_data["voice_over_track_name"] = None
        # Keep existing volume, or reset to default if preferred. Current behavior: keep.
        # sentence_data["voice_over_volume"] = DEFAULT_VOICE_OVER_VOLUME
        self.populate_sentence_table(select_row=current_row) # Refresh table
        self.voice_over_changed.emit(None, sentence_data.get("voice_over_volume", DEFAULT_VOICE_OVER_VOLUME))
        self.selected_sentence_vo_track_for_player.emit(None) # NEW
        self.sentences_updated.emit()


    def handle_vo_volume_changed(self, volume_float: float):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return

        sentences = self._get_sentences_list()
        sentence_data = sentences[current_row]
        if sentence_data.get("voice_over_track_name"): # Only change if a track is assigned
            if sentence_data.get("voice_over_volume") != volume_float:
                sentence_data["voice_over_volume"] = volume_float
                self.sentences_updated.emit()


    def get_current_sentence_count(self):
        return len(self._get_sentences_list())

    def get_selected_row(self):
        return self.sent_table_widget.currentRow()