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

logger = logging.getLogger(__name__)


class SentenceManager(QObject):
    sentences_updated = Signal()
    voice_over_changed = Signal(str, float)

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
        if not self.sent_table_widget.currentItem() and self.sent_table_widget.rowCount() == 0:
            self.voice_over_changed.emit(None, DEFAULT_VOICE_OVER_VOLUME)

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
                delay = sentence_data.get("delay_seconds", 0.1)
                text_item = QTableWidgetItem(text)
                self.sent_table_widget.setItem(i, 0, text_item)
                spin_box = QDoubleSpinBox()
                spin_box.setMinimum(0.0);
                spin_box.setMaximum(600.0)
                spin_box.setSingleStep(0.1);
                spin_box.setValue(delay)
                spin_box.setSuffix(" s");
                spin_box.setProperty("row", i)
                spin_box.valueChanged.connect(self.handle_delay_changed)
                self.sent_table_widget.setCellWidget(i, 1, spin_box)
            self.sent_table_widget.resizeRowsToContents()
        self._block_signals = False
        if select_row != -1 and 0 <= select_row < self.sent_table_widget.rowCount():
            self.sent_table_widget.selectRow(select_row)
        elif self.sent_table_widget.rowCount() > 0:
            self.sent_table_widget.selectRow(0)
        else:
            self._update_editor_state_for_selection()
            self.voice_over_changed.emit(None, DEFAULT_VOICE_OVER_VOLUME)
        self.editor_window.update_ui_state()

    def handle_delay_changed(self, value):
        if self._block_signals or not self.current_paragraph_data: return
        sender = self.sender()
        if sender:
            row = sender.property("row")
            sentences = self._get_sentences_list()
            if row is not None and 0 <= row < len(sentences):
                if sentences[row]["delay_seconds"] != value:
                    sentences[row]["delay_seconds"] = value
                    self.sentences_updated.emit()

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
            else:
                self.sent_edit_text.clear();
                self.sent_edit_text.setEnabled(False)
        else:
            self.sent_edit_text.clear();
            self.sent_edit_text.setEnabled(False)
        self._block_signals = False
        self.voice_over_changed.emit(vo_track_name, vo_volume)

    def handle_sent_selection_changed(self):
        self._update_editor_state_for_selection()
        self.editor_window.update_ui_state()

    def handle_sent_text_changed_from_table(self, item):
        if self._block_signals or not self.current_paragraph_data: return
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
                table_item = self.sent_table_widget.item(current_row, 0)
                if table_item:
                    table_item.setText(new_text)
                else:
                    self.sent_table_widget.setItem(current_row, 0, QTableWidgetItem(new_text))
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
                QMessageBox.warning(self.editor_window, "Split Error", "Cannot split into an empty sentence.");
                return
            sentences_list = self._get_sentences_list()
            if not (0 <= current_row < len(sentences_list)): return
            current_sentence_obj = sentences_list[current_row]
            current_delay = current_sentence_obj.get("delay_seconds", 2.0)
            current_sentence_obj["text"] = text1
            new_sentence_data = {"text": text2, "delay_seconds": current_delay / 2,
                                 "voice_over_track_name": None, "voice_over_volume": DEFAULT_VOICE_OVER_VOLUME}
            current_sentence_obj["delay_seconds"] = current_delay / 2
            insert_index = current_row + 1
            sentences_list.insert(insert_index, new_sentence_data)
            self.populate_sentence_table(select_row=insert_index);
            self.sentences_updated.emit()
        else:
            QMessageBox.information(self.editor_window, "Split Info", "Place cursor within text to split.")

    def join_sentence(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return
        sentences_list = self._get_sentences_list()
        if not (0 <= current_row < len(sentences_list) - 1):
            QMessageBox.information(self.editor_window, "Join Info", "Select a sentence not the last one.");
            return
        s1 = sentences_list[current_row];
        s2 = sentences_list[current_row + 1]
        t1 = s1.get("text", "").strip();
        t2 = s2.get("text", "").strip()
        s1["text"] = f"{t1} {t2}".strip() if t1 and t2 else (t1 or t2)
        s1["delay_seconds"] = s1.get("delay_seconds", 0) + s2.get("delay_seconds", 0)
        del sentences_list[current_row + 1]
        self.populate_sentence_table(select_row=current_row);
        self.sentences_updated.emit()

    def assign_voice_over_track(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data:
            QMessageBox.warning(self.editor_window, "No Sentence", "Please select a sentence first.")
            return

        available_tracks = sorted(self.track_manager.list_audio_tracks())
        if not available_tracks:
            QMessageBox.information(self.editor_window, "No Audio Tracks",
                                    "No audio tracks found. Import audio via main Control Window > Edit Playlist > Edit Audio Programs.")
            return

        track_name, ok = QInputDialog.getItem(self.editor_window, "Assign Voice-Over", "Select Audio Track:",
                                              available_tracks, 0, False)
        if ok and track_name:
            try:
                sentences = self._get_sentences_list()
                sentence_data = sentences[current_row]
                sentence_data["voice_over_track_name"] = track_name
                sentence_data.setdefault("voice_over_volume", DEFAULT_VOICE_OVER_VOLUME)
                # DELAY IS NO LONGER SET HERE AUTOMATICALLY

                self.populate_sentence_table(select_row=current_row)
                self.voice_over_changed.emit(track_name, sentence_data["voice_over_volume"])
                self.sentences_updated.emit()
                # Prompt user to use the "Set Time from VO" button
                QMessageBox.information(self.editor_window, "Track Assigned",
                                        f"Track '{track_name}' assigned.\nUse the 'Set Time from VO' button to update sentence duration if needed.")
            except Exception as e:
                logger.error(f"Error assigning voice over: {e}", exc_info=True)
                QMessageBox.critical(self.editor_window, "Error", f"Could not assign track: {e}")

    def set_delay_from_assigned_vo(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data:
            QMessageBox.warning(self.editor_window, "No Sentence", "Please select a sentence first.")
            return

        sentences = self._get_sentences_list()
        sentence_data = sentences[current_row]
        vo_track_name = sentence_data.get("voice_over_track_name")

        if not vo_track_name:
            QMessageBox.information(self.editor_window, "No Voice-Over",
                                    "No voice-over track assigned to this sentence.")
            return

        try:
            track_meta = self.track_manager.load_track_metadata(vo_track_name)

            # Check if metadata or duration is missing or invalid (0 or None)
            if not track_meta or track_meta.get("detected_duration_ms") is None or track_meta.get(
                    "detected_duration_ms") <= 0:
                QMessageBox.warning(self.editor_window, "Track Duration Error",
                                    f"Duration for '{vo_track_name}' is missing, zero, or invalid in its metadata file.\n"
                                    "Please ensure the track was imported correctly or edit its metadata if duration is incorrect.\n"
                                    "Sentence duration not changed.")
                return

            duration_ms = track_meta["detected_duration_ms"]
            duration_s = round(duration_ms / 1000.0, 1)

            sentence_data["delay_seconds"] = duration_s

            self.populate_sentence_table(select_row=current_row)
            self.sentences_updated.emit()
            logger.info(f"Set delay for sentence {current_row} to {duration_s}s from VO track '{vo_track_name}'.")

        except Exception as e:
            logger.error(f"Error setting delay from voice over: {e}", exc_info=True)
            QMessageBox.critical(self.editor_window, "Error", f"Could not set delay from track: {e}")

    def clear_voice_over_track(self):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return
        sentences = self._get_sentences_list()
        sentence_data = sentences[current_row]
        sentence_data["voice_over_track_name"] = None
        self.populate_sentence_table(select_row=current_row)
        self.voice_over_changed.emit(None, sentence_data.get("voice_over_volume", DEFAULT_VOICE_OVER_VOLUME))
        self.sentences_updated.emit()

    def handle_vo_volume_changed(self, volume_float: float):
        current_row = self.sent_table_widget.currentRow()
        if current_row == -1 or not self.current_paragraph_data: return
        sentences = self._get_sentences_list()
        sentence_data = sentences[current_row]
        if sentence_data.get("voice_over_track_name"):
            if sentence_data.get("voice_over_volume") != volume_float:
                sentence_data["voice_over_volume"] = volume_float
                self.sentences_updated.emit()

    def get_current_sentence_count(self):
        return len(self._get_sentences_list())

    def get_selected_row(self):
        return self.sent_table_widget.currentRow()