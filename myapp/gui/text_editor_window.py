# myapp/gui/text_editor_window.py
import os
import logging
import copy
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QMessageBox, QInputDialog,
    QSplitter, QLabel, QGroupBox, QTextEdit, QTableWidget,
    QHeaderView, QAbstractItemView, QSlider, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer  # Added for media status enum access

from ..text.paragraph_manager import ParagraphManager
from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_icon_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component
from .sentence_manager import SentenceManager
from .text_import_dialog import TextImportDialog
from .audio_import_dialog import AudioImportDialog
from .sentence_vo_player_panel import SentenceVOPlayerPanel
from ..utils.schemas import DEFAULT_VOICE_OVER_VOLUME
from .help_window import HelpWindow
logger = logging.getLogger(__name__)


class TextEditorWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Initializing TextEditorWindow...")
        self.setWindowTitle("Text Paragraph Editor [*]")
        self.setGeometry(150, 150, 900, 850)
        self.setWindowModified(False)
        self.help_window_instance = None
        self.paragraph_manager = ParagraphManager()
        self.track_manager = AudioTrackManager()
        self.paragraphs_cache = {}
        self.current_paragraph_name = None
        self._block_list_signals = False

        self._setup_ui()

        self.sentence_manager.sentences_updated.connect(lambda: self.mark_dirty(True))
        self.sentence_manager.voice_over_changed.connect(self.update_voice_over_ui_for_selection)
        self.sentence_manager.selected_sentence_vo_track_for_player.connect(self.sentence_vo_player_panel.load_vo_track)

        self.sentence_vo_player_panel.duration_ready.connect(self.update_ui_state)

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
        self._set_window_icon()
        logger.debug("TextEditorWindow UI setup complete.")

    def _set_window_icon(self):
        try:
            icon_path = get_icon_file_path("text.png") or get_icon_file_path("edit.png")
            if icon_path and os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set TextEditorWindow icon: {e}", exc_info=True)

    def _setup_paragraph_panel(self, splitter):
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Paragraphs:"))
        self.para_list_widget = QListWidget()
        self.para_list_widget.currentItemChanged.connect(self.handle_para_selection_changed)
        left_layout.addWidget(self.para_list_widget)
        para_buttons_layout_row1 = QHBoxLayout()
        self.add_para_button = create_button("Add", "add.png", "Add New Paragraph", self.add_paragraph)
        self.import_para_button = create_button("Import Txt", "import.png", "Import Text File",
                                                self.open_text_import_dialog)
        self.rename_para_button = create_button("Rename", "edit.png", "Rename Selected Paragraph",
                                                self.rename_paragraph)
        para_buttons_layout_row1.addWidget(self.add_para_button)
        para_buttons_layout_row1.addWidget(self.import_para_button)
        para_buttons_layout_row1.addWidget(self.rename_para_button)
        left_layout.addLayout(para_buttons_layout_row1)
        para_buttons_layout_row2 = QHBoxLayout()
        self.help_button = create_button("", "help.png", "Help for this window", self.open_help_window)
        self.duplicate_para_button = create_button("Duplicate", "duplicate.png", "Duplicate Selected Paragraph",
                                                   self.duplicate_paragraph)
        self.del_para_button = create_button("Delete", "remove.png", "Delete Selected Paragraph", self.delete_paragraph)

        para_buttons_layout_row2.addWidget(self.help_button)

        para_buttons_layout_row2.addWidget(self.duplicate_para_button)
        para_buttons_layout_row2.addStretch()
        para_buttons_layout_row2.addWidget(self.del_para_button)
        left_layout.addLayout(para_buttons_layout_row2)
        splitter.addWidget(left_widget)

    def open_help_window(self):
        if self.help_window_instance is None or not self.help_window_instance.isVisible():
            self.help_window_instance = HelpWindow(self, anchor="text_editor")
            self.help_window_instance.show()
        else:
            self.help_window_instance.activateWindow()
            self.help_window_instance.raise_()

    def _setup_sentence_panel(self, splitter):
        right_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_widget)

        top_right_buttons_layout = QHBoxLayout()
        top_right_buttons_layout.addStretch()
        self.save_button = create_button("Save All Changes", "save.png", on_click=self.save_all_changes)
        self.done_button = create_button("Done", "done.png", on_click=self.close)
        top_right_buttons_layout.addWidget(self.save_button)
        top_right_buttons_layout.addWidget(self.done_button)
        right_panel_layout.addLayout(top_right_buttons_layout)

        self.para_group_box = QGroupBox("Edit Sentences")
        sentence_editing_layout = QVBoxLayout(self.para_group_box)
        self.para_name_label = QLabel("Paragraph: (None)")
        self.para_name_label.setStyleSheet("font-weight: bold;")
        sentence_editing_layout.addWidget(self.para_name_label)
        sentence_editing_layout.addWidget(QLabel("Sentences (Drag Row Header to Reorder):"))
        self.sent_table_widget = QTableWidget()
        self.sent_edit_text = QTextEdit()
        self.sentence_manager = SentenceManager(self, self.sent_table_widget, self.sent_edit_text, self.track_manager)

        self.sent_table_widget.setColumnCount(2)
        self.sent_table_widget.setHorizontalHeaderLabels(["Sentence Text", "Duration (s)"])
        self.sent_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.sent_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.sent_table_widget.verticalHeader().setSectionsMovable(True)
        self.sent_table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sent_table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        sentence_editing_layout.addWidget(self.sent_table_widget)
        sent_buttons_layout1 = QHBoxLayout()
        self.add_sent_button = create_button("Add Sent.", "add.png", "Add Sentence",
                                             lambda: self.sentence_manager.add_sentence())
        self.duplicate_sent_button = create_button("Dup. Sent.", "duplicate.png", "Duplicate Selected Sentence",
                                                   lambda: self.sentence_manager.duplicate_sentence())
        self.del_sent_button = create_button("Del. Sent.", "remove.png", "Remove Selected Sentence",
                                             lambda: self.sentence_manager.delete_sentence())
        sent_buttons_layout1.addWidget(self.add_sent_button)
        sent_buttons_layout1.addWidget(self.duplicate_sent_button)
        sent_buttons_layout1.addWidget(self.del_sent_button)
        sent_buttons_layout1.addStretch()
        sentence_editing_layout.addLayout(sent_buttons_layout1)
        sent_buttons_layout2 = QHBoxLayout()
        sent_buttons_layout2.addStretch()
        self.split_sent_button = create_button("Split", "split.png", "Split Sentence at Cursor",
                                               lambda: self.sentence_manager.split_sentence())
        self.join_sent_button = create_button("Join", "join.png", "Join Selected Sentence with Next",
                                              lambda: self.sentence_manager.join_sentence())
        self.blank_sent_button = create_button("Blank", "blank.png", "Insert Blank Sentence After Selected",
                                               lambda: self.sentence_manager.insert_blank_sentence())
        sent_buttons_layout2.addWidget(self.split_sent_button)
        sent_buttons_layout2.addWidget(self.join_sent_button)
        sent_buttons_layout2.addWidget(self.blank_sent_button)
        sentence_editing_layout.addLayout(sent_buttons_layout2)
        sentence_editing_layout.addWidget(QLabel("Edit Selected Sentence Text:"))
        sentence_editing_layout.addWidget(self.sent_edit_text)
        right_panel_layout.addWidget(self.para_group_box)

        self.vo_assign_group_box = QGroupBox("Sentence Voice-Over Assignment")
        self.vo_assign_group_box.setEnabled(False)
        vo_assign_layout = QFormLayout(self.vo_assign_group_box)
        self.vo_track_name_label = QLabel("(None)")
        vo_assign_layout.addRow("Assigned Track:", self.vo_track_name_label)
        vo_buttons_layout = QHBoxLayout()
        self.vo_assign_button = create_button("Assign/Change...", "audio_icon.png",
                                              on_click=lambda: self.sentence_manager.assign_voice_over_track())
        self.vo_import_assign_button = create_button("Import & Assign...", "import.png",
                                                     on_click=self._handle_import_and_assign_vo)
        self.vo_clear_button = create_button("Clear Track", "remove.png",
                                             on_click=lambda: self.sentence_manager.clear_voice_over_track())
        vo_buttons_layout.addWidget(self.vo_assign_button)
        vo_buttons_layout.addWidget(self.vo_import_assign_button)
        vo_buttons_layout.addWidget(self.vo_clear_button)
        vo_assign_layout.addRow(vo_buttons_layout)
        vo_volume_layout = QHBoxLayout()
        self.vo_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.vo_volume_slider.setRange(0, 100);
        self.vo_volume_slider.setValue(int(DEFAULT_VOICE_OVER_VOLUME * 100))
        self.vo_volume_slider.valueChanged.connect(self._handle_vo_volume_slider_changed)
        self.vo_volume_label = QLabel(f"{self.vo_volume_slider.value()}%")
        vo_volume_layout.addWidget(self.vo_volume_slider);
        vo_volume_layout.addWidget(self.vo_volume_label)
        vo_assign_layout.addRow("Volume:", vo_volume_layout)
        right_panel_layout.addWidget(self.vo_assign_group_box)

        self.sentence_vo_player_panel = SentenceVOPlayerPanel(self.track_manager, self)
        self.sentence_vo_player_panel.setEnabled(False)
        self.sentence_vo_player_panel.playback_error_occurred.connect(
            lambda msg: QMessageBox.warning(self, "Voice-Over Playback Error", msg)
        )
        right_panel_layout.addWidget(self.sentence_vo_player_panel)

        self.vo_set_time_button = create_button("Set Sentence Duration from Player", "timer_icon.png",
                                                "Set sentence duration from current V/O player's track duration. Prompts to update metadata if different.",
                                                on_click=self._handle_set_duration_from_vo_player)
        self.vo_set_time_button.setEnabled(False)
        right_panel_layout.addWidget(self.vo_set_time_button)

        right_panel_layout.addStretch()
        splitter.addWidget(right_widget)

    def _handle_import_and_assign_vo(self):
        if self.sentence_manager.get_selected_row() == -1:
            QMessageBox.warning(self, "No Sentence", "Please select a sentence first.")
            return
        self.sentence_manager.import_and_assign_track_to_selected_sentence(self)

    def _handle_set_duration_from_vo_player(self):
        selected_row = self.sentence_manager.get_selected_row()
        if selected_row == -1:
            QMessageBox.warning(self, "No Sentence", "Please select a sentence to set duration for.")
            return

        sentence_data = self.sentence_manager.get_sentence_data(selected_row)
        if not sentence_data: return
        vo_track_name = sentence_data.get("voice_over_track_name")

        if not vo_track_name:
            QMessageBox.information(self, "No Voice-Over", "No voice-over track assigned to this sentence.")
            return

        player_duration_ms = self.sentence_vo_player_panel.get_current_track_duration_ms_from_player()

        if player_duration_ms is None or player_duration_ms <= 0:
            QMessageBox.warning(self, "Player Duration Error",
                                "Could not get a valid duration from the V/O player for the current track.\n"
                                "Ensure the track is loaded and playable in the panel above.")
            return

        try:
            track_meta = self.track_manager.load_track_metadata(vo_track_name)
            if not track_meta:
                QMessageBox.critical(self, "Metadata Error", f"Could not load metadata for track '{vo_track_name}'.")
                return

            metadata_duration_ms = track_meta.get("detected_duration_ms")
            final_duration_to_set_ms = player_duration_ms

            if metadata_duration_ms is None or metadata_duration_ms <= 0 or metadata_duration_ms != player_duration_ms:
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Question)
                msg_box.setWindowTitle("Update Track Metadata?")
                text = (f"The player's duration for '{vo_track_name}' is <b>{player_duration_ms / 1000.0:.1f}s</b>.<br>"
                        f"The stored metadata duration is <b>{(metadata_duration_ms / 1000.0):.1f}s</b> (or not set).<br><br>"
                        f"Do you want to update the track's metadata file (<i>{vo_track_name}.json</i>) "
                        f"with the player's duration (<b>{player_duration_ms / 1000.0:.1f}s</b>)?")
                msg_box.setText(text)
                update_button = msg_box.addButton("Update Metadata & Set Sentence", QMessageBox.ButtonRole.YesRole)
                set_only_button = msg_box.addButton("Set Sentence Only (Use Player Duration)",
                                                    QMessageBox.ButtonRole.NoRole)
                msg_box.addButton(QMessageBox.StandardButton.Cancel)
                msg_box.setDefaultButton(update_button)
                msg_box.exec()

                clicked_button = msg_box.clickedButton()
                if clicked_button == update_button:
                    track_meta["detected_duration_ms"] = player_duration_ms
                    if self.track_manager.save_track_metadata(vo_track_name, track_meta):
                        logger.info(f"Updated metadata for '{vo_track_name}' with duration {player_duration_ms}ms.")
                        QMessageBox.information(self, "Metadata Updated",
                                                f"Track metadata for '{vo_track_name}' updated.")
                    else:
                        QMessageBox.warning(self, "Metadata Save Failed",
                                            f"Could not save updated metadata for '{vo_track_name}'. Sentence duration will use player's duration for now.")
                elif clicked_button == QMessageBox.StandardButton.Cancel:
                    return

            self.sentence_manager.set_sentence_delay_seconds(selected_row, final_duration_to_set_ms / 1000.0)
            logger.info(
                f"Set delay for sentence {selected_row} to {final_duration_to_set_ms / 1000.0:.1f}s from V/O player.")

        except Exception as e:
            logger.error(f"Error in _handle_set_duration_from_vo_player: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def _handle_vo_volume_slider_changed(self, value):
        self.vo_volume_label.setText(f"{value}%")
        self.sentence_manager.handle_vo_volume_changed(value / 100.0)
        if self.sentence_vo_player_panel.current_loaded_track_meta_name:
            self.sentence_vo_player_panel.set_volume(value / 100.0)

    def update_voice_over_ui_for_selection(self, track_name, volume):
        has_selection = self.sentence_manager.get_selected_row() != -1
        self.vo_assign_group_box.setEnabled(has_selection)
        has_vo_track = bool(track_name)

        if has_selection and has_vo_track:
            self.vo_track_name_label.setText(track_name)
            self.vo_volume_slider.setValue(int((volume if volume is not None else DEFAULT_VOICE_OVER_VOLUME) * 100))
            self.vo_volume_label.setText(f"{self.vo_volume_slider.value()}%")
            self.vo_volume_slider.setEnabled(True)
            self.vo_clear_button.setEnabled(True)
        elif has_selection:
            self.vo_track_name_label.setText("(None)")
            self.vo_volume_slider.setValue(int(DEFAULT_VOICE_OVER_VOLUME * 100))
            self.vo_volume_label.setText(f"{self.vo_volume_slider.value()}%")
            self.vo_volume_slider.setEnabled(False)
            self.vo_clear_button.setEnabled(False)
        else:
            self.vo_track_name_label.setText("(No sentence selected)")
            self.vo_volume_slider.setEnabled(False)
            self.vo_clear_button.setEnabled(False)
            self.vo_volume_slider.setValue(int(DEFAULT_VOICE_OVER_VOLUME * 100))
            self.vo_volume_label.setText(f"{self.vo_volume_slider.value()}%")

        self.update_ui_state()

    def open_text_import_dialog(self):
        logger.debug("Open text import dialog called.")
        import_dialog = TextImportDialog(self, self.paragraph_manager)
        import_dialog.paragraph_imported.connect(self._handle_paragraph_imported)
        import_dialog.exec()

    def _handle_paragraph_imported(self, new_paragraph_name):
        logger.info(f"Paragraph '{new_paragraph_name}' was imported/created. Refreshing list.")
        self.load_and_list_paragraphs(select_program_name=new_paragraph_name)

    def mark_dirty(self, dirty=True):
        self.setWindowModified(dirty)
        self.update_ui_state()

    def load_and_list_paragraphs(self, select_program_name=None):
        logger.debug(f"Loading and listing paragraphs. Target selection: '{select_program_name}'")
        current_selection_name = select_program_name if select_program_name else self.current_paragraph_name

        self._block_list_signals = True
        try:
            self.para_list_widget.currentItemChanged.disconnect(self.handle_para_selection_changed)
        except RuntimeError:
            pass
        self.para_list_widget.clear()
        self.para_list_widget.currentItemChanged.connect(self.handle_para_selection_changed)
        self._block_list_signals = False

        try:
            para_names = sorted(self.paragraph_manager.list_paragraphs())
            if not para_names:
                self.current_paragraph_name = None
                self.sentence_manager.set_current_paragraph(None, None)
                self.para_name_label.setText("Paragraph: (None)")
                self.update_voice_over_ui_for_selection(None, DEFAULT_VOICE_OVER_VOLUME)
                self.update_ui_state();
                return

            self.para_list_widget.addItems(para_names)
            restored_selection = False
            if current_selection_name and current_selection_name in para_names:
                for i in range(self.para_list_widget.count()):
                    if self.para_list_widget.item(i).text() == current_selection_name:
                        self._block_list_signals = True
                        self.para_list_widget.setCurrentRow(i)
                        self._block_list_signals = False
                        restored_selection = True;
                        break

            if not restored_selection and self.para_list_widget.count() > 0:
                self._block_list_signals = True
                self.para_list_widget.setCurrentRow(0)
                self._block_list_signals = False

            if self.para_list_widget.currentItem():
                self.handle_para_selection_changed(self.para_list_widget.currentItem(), None)
            else:
                self.handle_para_selection_changed(None, None)

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to list paragraphs: {e}")
            self.current_paragraph_name = None
            self.sentence_manager.set_current_paragraph(None, None)
            self.para_name_label.setText("Paragraph: (None)")
            self.update_voice_over_ui_for_selection(None, DEFAULT_VOICE_OVER_VOLUME)
        self.update_ui_state()

    def handle_para_selection_changed(self, current_item, previous_item):
        if self._block_list_signals: return

        if not current_item:
            self.current_paragraph_name = None
            self.sentence_manager.set_current_paragraph(None, None)
            self.para_name_label.setText("Paragraph: (None)")
            self.sentence_vo_player_panel.load_vo_track(None)
            self.update_voice_over_ui_for_selection(None, DEFAULT_VOICE_OVER_VOLUME)
            self.update_ui_state()
            return

        selected_para_name = current_item.text()
        if selected_para_name == self.current_paragraph_name and self.current_paragraph_name in self.paragraphs_cache:
            self.sentence_manager.set_current_paragraph(self.current_paragraph_name,
                                                        self.paragraphs_cache[self.current_paragraph_name])
            self.sentence_manager.handle_sent_selection_changed()
            self.update_ui_state()
            return

        self.current_paragraph_name = selected_para_name
        logger.info(f"Paragraph selected: {self.current_paragraph_name}")

        if self.current_paragraph_name not in self.paragraphs_cache:
            try:
                self.paragraphs_cache[self.current_paragraph_name] = self.paragraph_manager.load_paragraph(
                    self.current_paragraph_name)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load '{self.current_paragraph_name}': {e}")
                self.paragraphs_cache.pop(self.current_paragraph_name, None)
                current_row = self.para_list_widget.currentRow()
                if current_row != -1: self.para_list_widget.takeItem(current_row)

                self._block_list_signals = True
                if self.para_list_widget.count() > 0:
                    self.para_list_widget.setCurrentRow(0)
                else:
                    self.handle_para_selection_changed(None, None)
                self._block_list_signals = False
                if self.para_list_widget.currentItem(): self.handle_para_selection_changed(
                    self.para_list_widget.currentItem(), None)
                return

        if self.current_paragraph_name and self.current_paragraph_name in self.paragraphs_cache:
            self.sentence_manager.set_current_paragraph(self.current_paragraph_name,
                                                        self.paragraphs_cache[self.current_paragraph_name])
            self.para_name_label.setText(f"Paragraph: {self.current_paragraph_name}")
        else:
            self.sentence_manager.set_current_paragraph(None, None)
            self.para_name_label.setText("Paragraph: (None)")
            self.sentence_vo_player_panel.load_vo_track(None)
            self.update_voice_over_ui_for_selection(None, DEFAULT_VOICE_OVER_VOLUME)
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
                self.paragraphs_cache[safe_name] = new_para_data
                self._handle_paragraph_imported(safe_name)
            else:
                QMessageBox.critical(self, "Save Error", "Could not save the new paragraph.")

    def duplicate_paragraph(self):
        if not self.current_paragraph_name:
            QMessageBox.information(self, "Duplicate Paragraph", "Please select a paragraph to duplicate.");
            return
        original_name = self.current_paragraph_name
        try:
            original_data = self.paragraphs_cache.get(original_name)
            if not original_data: original_data = self.paragraph_manager.load_paragraph(original_name)
            if not original_data: QMessageBox.critical(self, "Error",
                                                       f"Could not load data for '{original_name}'."); return
            base_name = original_name;
            count = 1;
            new_name = f"{base_name}_{count:02d}"
            existing_names = self.paragraph_manager.list_paragraphs()
            while new_name in existing_names: count += 1; new_name = f"{base_name}_{count:02d}"
            new_paragraph_data = copy.deepcopy(original_data);
            new_paragraph_data["name"] = new_name
            if self.paragraph_manager.save_paragraph(new_name, new_paragraph_data):
                self.paragraphs_cache[new_name] = new_paragraph_data;
                self._handle_paragraph_imported(new_name)
                QMessageBox.information(self, "Paragraph Duplicated",
                                        f"Paragraph '{original_name}' duplicated as '{new_name}'.")
            else:
                QMessageBox.critical(self, "Save Error", f"Could not save duplicated paragraph '{new_name}'.")
        except Exception as e:
            logger.error(f"Error duplicating paragraph '{original_name}': {e}", exc_info=True); QMessageBox.critical(
                self, "Duplicate Error", f"An error occurred: {e}")

    def rename_paragraph(self):
        current_list_item = self.para_list_widget.currentItem()
        if not current_list_item or not self.current_paragraph_name: return
        old_name = self.current_paragraph_name
        new_name_input, ok = QInputDialog.getText(self, "Rename Paragraph", f"New name for '{old_name}':",
                                                  text=old_name)
        if not (ok and new_name_input and new_name_input.strip()): return
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
            if not current_data: current_data = self.paragraph_manager.load_paragraph(old_name)
            current_data["name"] = safe_new_name
            if self.paragraph_manager.save_paragraph(safe_new_name, current_data):
                if old_name.lower() != safe_new_name.lower(): self.paragraph_manager.delete_paragraph(old_name)
                if old_name in self.paragraphs_cache: del self.paragraphs_cache[old_name]
                self.paragraphs_cache[safe_new_name] = current_data;
                self._handle_paragraph_imported(safe_new_name)
            else:
                current_data["name"] = old_name; QMessageBox.critical(self, "Save Error",
                                                                      "Could not save paragraph with the new name.")
        except Exception as e:
            QMessageBox.critical(self, "Rename Error", f"Failed to rename paragraph: {e}")

    def delete_paragraph(self):
        if not self.current_paragraph_name: return
        para_name_to_delete = self.current_paragraph_name
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete '{para_name_to_delete}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.paragraph_manager.delete_paragraph(para_name_to_delete):
                if para_name_to_delete in self.paragraphs_cache: del self.paragraphs_cache[para_name_to_delete]
                self.current_paragraph_name = None
                self.sentence_vo_player_panel.load_vo_track(None)
                self.load_and_list_paragraphs()
            else:
                QMessageBox.critical(self, "Delete Error", "Could not delete paragraph file.")

    def save_all_changes(self):
        logger.info("Saving all changes...")
        if not self.isWindowModified():
            QMessageBox.information(self, "No Changes", "No changes to save.");
            return
        if self.current_paragraph_name and self.current_paragraph_name in self.paragraphs_cache and self.sentence_manager.current_paragraph_data:
            self.paragraphs_cache[self.current_paragraph_name][
                "sentences"] = self.sentence_manager._get_sentences_list()
        saved_count, failed_count = 0, 0
        for name, data in self.paragraphs_cache.items():
            if data:
                try:
                    if data.get("name") != name: data["name"] = name
                    if self.paragraph_manager.save_paragraph(name, data):
                        saved_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error saving paragraph '{name}': {e}", exc_info=True); failed_count += 1
        if failed_count > 0: QMessageBox.warning(self, "Save Error",
                                                 f"Failed to save {failed_count} paragraph(s). Check logs.")
        if saved_count > 0: QMessageBox.information(self, "Save Complete",
                                                    f"Successfully saved {saved_count} paragraph(s).")
        if failed_count == 0:
            self.mark_dirty(False)
        else:
            QMessageBox.information(self, "Save Status", "Some changes might not have been saved.")

    def update_ui_state(self):
        logger.debug(f"TextEditorWindow.update_ui_state() called. Current paragraph: {self.current_paragraph_name}")
        para_selected = self.current_paragraph_name is not None
        sent_selected_row = -1
        num_sentences = 0
        has_vo_track_on_selected_sentence = False

        if self.sentence_manager:
            sent_selected_row = self.sentence_manager.get_selected_row()
            num_sentences = self.sentence_manager.get_current_sentence_count()
            if sent_selected_row != -1:
                current_sent_data = self.sentence_manager.get_sentence_data(sent_selected_row)
                if current_sent_data:
                    has_vo_track_on_selected_sentence = bool(current_sent_data.get("voice_over_track_name"))
        sent_selected = para_selected and sent_selected_row != -1

        player_current_duration_ms = self.sentence_vo_player_panel.get_current_track_duration_ms_from_player()
        player_has_valid_duration = player_current_duration_ms is not None and player_current_duration_ms > 0

        # More detailed log for the button in question
        logger.debug(
            f"  vo_set_time_button conditions: "
            f"sent_selected={sent_selected}, "
            f"has_vo_track={has_vo_track_on_selected_sentence}, "
            f"player_has_valid_duration={player_has_valid_duration} "
            f"(player_current_duration_ms from getter: {player_current_duration_ms}, "
            f"panel.current_track_duration_ms_from_player: {self.sentence_vo_player_panel.current_track_duration_ms_from_player}, "
            f"panel.media_player.mediaStatus(): {self.sentence_vo_player_panel.media_player.mediaStatus()})"
        )

        self.rename_para_button.setEnabled(para_selected)
        self.del_para_button.setEnabled(para_selected)
        self.duplicate_para_button.setEnabled(para_selected)
        self.para_group_box.setEnabled(para_selected)
        self.add_sent_button.setEnabled(para_selected)
        self.del_sent_button.setEnabled(sent_selected)
        self.duplicate_sent_button.setEnabled(sent_selected)
        self.blank_sent_button.setEnabled(para_selected)
        can_split = sent_selected and self.sent_edit_text.isEnabled() and len(self.sent_edit_text.toPlainText()) > 0
        self.split_sent_button.setEnabled(can_split)
        is_last_sentence = (sent_selected_row == num_sentences - 1) if num_sentences > 0 and sent_selected else False
        can_join = sent_selected and (num_sentences > 1 and not is_last_sentence)
        self.join_sent_button.setEnabled(can_join)
        self.sent_edit_text.setEnabled(sent_selected)
        self.save_button.setEnabled(self.isWindowModified())
        self.vo_assign_group_box.setEnabled(sent_selected)
        self.vo_assign_button.setEnabled(sent_selected)
        self.vo_import_assign_button.setEnabled(sent_selected)
        self.vo_clear_button.setEnabled(sent_selected and has_vo_track_on_selected_sentence)
        self.vo_volume_slider.setEnabled(sent_selected and has_vo_track_on_selected_sentence)
        self.vo_volume_label.setEnabled(sent_selected and has_vo_track_on_selected_sentence)
        self.sentence_vo_player_panel.setEnabled(sent_selected and has_vo_track_on_selected_sentence)
        self.vo_set_time_button.setEnabled(
            sent_selected and has_vo_track_on_selected_sentence and player_has_valid_duration)

    def prompt_save_changes(self):
        if not self.isWindowModified(): return True
        reply = QMessageBox.question(self, 'Unsaved Changes', "There are unsaved changes. Save them now?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)
        if reply == QMessageBox.StandardButton.Save: self.save_all_changes(); return not self.isWindowModified()
        return reply == QMessageBox.StandardButton.Discard

    def closeEvent(self, event):
        logger.debug("TextEditorWindow closeEvent triggered.")
        if self.sentence_vo_player_panel and self.sentence_vo_player_panel.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.sentence_vo_player_panel._stop_playback(internal_call=True)
        if self.prompt_save_changes():
            event.accept(); logger.info("TextEditorWindow closing.")
        else:
            event.ignore(); logger.info("TextEditorWindow close cancelled by user.")