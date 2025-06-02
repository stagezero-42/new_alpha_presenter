# myapp/gui/audio_track_in_program_manager.py
import logging
from PySide6.QtWidgets import (
    QTableWidgetItem, QDoubleSpinBox, QMessageBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QObject

logger = logging.getLogger(__name__)


class AudioTrackInProgramManager(QObject):
    program_tracks_updated = Signal()

    COL_TRACK_NAME = 0
    COL_START_TIME = 1
    COL_END_TIME = 2

    def __init__(self, editor_window, tracks_table_widget):
        super().__init__()
        self.editor_window = editor_window  # This is the AudioProgramEditorWindow instance
        self.tracks_table_widget = tracks_table_widget

        self.current_program_name = None
        self.current_program_data = None
        self._block_signals = False

        # This connection is made in AudioProgramEditorWindow now,
        # connecting tracks_table_widget.itemSelectionChanged to
        # AudioProgramEditorWindow._handle_track_table_selection_changed
        # So, we don't need self.tracks_table_widget.itemSelectionChanged.connect(self.handle_track_selection_changed) here.
        # self.tracks_table_widget.itemSelectionChanged.connect(self.handle_track_selection_changed)

        self.tracks_table_widget.verticalHeader().sectionMoved.connect(self.handle_track_reorder)

        self.tracks_table_widget.setColumnCount(3)
        self.tracks_table_widget.setHorizontalHeaderLabels(["Track Name", "Start (ms)", "End (ms)"])
        self.tracks_table_widget.horizontalHeader().setSectionResizeMode(self.COL_TRACK_NAME,
                                                                         self.tracks_table_widget.horizontalHeader().ResizeMode.Stretch)
        self.tracks_table_widget.horizontalHeader().setSectionResizeMode(self.COL_START_TIME,
                                                                         self.tracks_table_widget.horizontalHeader().ResizeMode.ResizeToContents)
        self.tracks_table_widget.horizontalHeader().setSectionResizeMode(self.COL_END_TIME,
                                                                         self.tracks_table_widget.horizontalHeader().ResizeMode.ResizeToContents)
        self.tracks_table_widget.verticalHeader().setSectionsMovable(True)
        self.tracks_table_widget.setSelectionBehavior(self.tracks_table_widget.SelectionBehavior.SelectRows)
        self.tracks_table_widget.setSelectionMode(self.tracks_table_widget.SelectionMode.SingleSelection)

    def set_current_program(self, program_name, program_data):
        self.current_program_name = program_name
        self.current_program_data = program_data
        self.populate_tracks_table()
        # _update_editor_tools_for_selection is implicitly handled by selection change in AudioProgramEditorWindow

    def _get_program_tracks_list(self):
        if self.current_program_data and isinstance(self.current_program_data.get("tracks"), list):
            return self.current_program_data["tracks"]
        elif self.current_program_data:
            self.current_program_data["tracks"] = []
            return self.current_program_data["tracks"]
        return []

    def populate_tracks_table(self, select_row=-1):
        self._block_signals = True
        self.tracks_table_widget.clearContents()
        self.tracks_table_widget.setRowCount(0)

        if self.current_program_data:
            program_tracks = self._get_program_tracks_list()
            program_tracks.sort(key=lambda t: t.get("play_order", 0))

            self.tracks_table_widget.setRowCount(len(program_tracks))
            for i, track_entry_data in enumerate(program_tracks):
                track_entry_data["play_order"] = i

                track_name = track_entry_data.get("track_name", "[Missing Track]")
                start_ms = track_entry_data.get("user_start_time_ms", 0)
                end_ms_val = track_entry_data.get("user_end_time_ms")

                name_item = QTableWidgetItem(track_name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tracks_table_widget.setItem(i, self.COL_TRACK_NAME, name_item)

                start_spin = QSpinBox()
                start_spin.setRange(0, 3600 * 1000 * 24);
                start_spin.setSuffix(" ms")
                start_spin.setValue(start_ms)
                start_spin.setProperty("row", i);
                start_spin.setProperty("col", self.COL_START_TIME)
                start_spin.valueChanged.connect(self._handle_time_spinbox_changed)
                self.tracks_table_widget.setCellWidget(i, self.COL_START_TIME, start_spin)

                end_spin = QSpinBox()
                end_spin.setRange(0, 3600 * 1000 * 24);
                end_spin.setSuffix(" ms")
                end_spin.setSpecialValueText("Track End")
                end_spin.setValue(end_ms_val if end_ms_val is not None else 0)
                end_spin.setProperty("row", i);
                end_spin.setProperty("col", self.COL_END_TIME)
                end_spin.valueChanged.connect(self._handle_time_spinbox_changed)
                self.tracks_table_widget.setCellWidget(i, self.COL_END_TIME, end_spin)

            self.tracks_table_widget.resizeRowsToContents()

        self._block_signals = False
        if select_row != -1 and self.tracks_table_widget.rowCount() > 0:
            actual_row = min(select_row, self.tracks_table_widget.rowCount() - 1)
            self.tracks_table_widget.selectRow(actual_row)  # This triggers itemSelectionChanged

        # The call to _update_editor_tools_for_selection() is removed from here.
        # The main AudioProgramEditorWindow._handle_track_table_selection_changed
        # will handle updating the player panel when selectRow() causes a selection change.
        # If no row is selected initially, AudioProgramEditorWindow should also handle
        # clearing/disabling the player panel.

    def _handle_time_spinbox_changed(self, value):
        if self._block_signals or not self.current_program_data: return
        sender_spinbox = self.sender()
        if not sender_spinbox: return

        row = sender_spinbox.property("row")
        col = sender_spinbox.property("col")
        program_tracks = self._get_program_tracks_list()

        if 0 <= row < len(program_tracks):
            track_entry = program_tracks[row]
            changed = False
            if col == self.COL_START_TIME:
                if track_entry["user_start_time_ms"] != value:
                    track_entry["user_start_time_ms"] = value
                    changed = True
                    end_spin = self.tracks_table_widget.cellWidget(row, self.COL_END_TIME)
                    if end_spin and end_spin.value() != 0 and value > end_spin.value():
                        end_spin.setValue(value)  # This will trigger its own valueChanged
                        # track_entry["user_end_time_ms"] = value # Handled by end_spin's signal
            elif col == self.COL_END_TIME:
                new_end_val = value if value != 0 else None
                if track_entry["user_end_time_ms"] != new_end_val:
                    track_entry["user_end_time_ms"] = new_end_val
                    changed = True
                    start_spin_val = track_entry.get("user_start_time_ms", 0)
                    if value != 0 and value < start_spin_val:  # Ensure end is not before start
                        sender_spinbox.setValue(start_spin_val)  # Revert to start_time
                        # track_entry["user_end_time_ms"] = start_spin_val # Handled by setValue signal

            if changed:
                self.program_tracks_updated.emit()
                # self.editor_window.update_ui_state() # Let AudioProgramEditorWindow handle this via its own slots

    # This method is no longer strictly needed for player UI updates,
    # as AudioProgramEditorWindow handles it.
    # It can be removed or kept if it serves other purposes for enabling/disabling
    # tools directly managed by AudioTrackInProgramManager in the future.
    # For now, let's simplify/remove its problematic content.
    def _update_editor_tools_for_selection(self):
        # This method's responsibility to call editor_window.update_audio_player_ui_for_track
        # has been moved to AudioProgramEditorWindow._handle_track_table_selection_changed
        # logger.debug("AudioTrackInProgramManager: _update_editor_tools_for_selection called.")
        pass

    # This method is also effectively replaced by AudioProgramEditorWindow._handle_track_table_selection_changed
    # def handle_track_selection_changed(self):
    #     logger.debug("AudioTrackInProgramManager: handle_track_selection_changed called.")
    #     self._update_editor_tools_for_selection()
    #     if hasattr(self.editor_window, 'update_ui_state'): # Call if editor window has it
    #          self.editor_window.update_ui_state()

    def handle_track_reorder(self, logical_old_index, old_visual_index, new_visual_index):
        if self._block_signals or not self.current_program_data or old_visual_index == new_visual_index: return
        logger.debug(f"Track row visually moved from {old_visual_index} to {new_visual_index}")

        program_tracks = self._get_program_tracks_list()
        moved_track_entry = program_tracks.pop(old_visual_index)
        program_tracks.insert(new_visual_index, moved_track_entry)
        for i, track_entry in enumerate(program_tracks):
            track_entry["play_order"] = i

        self.program_tracks_updated.emit()
        self.populate_tracks_table(select_row=new_visual_index)

    def add_track_to_program(self, track_metadata_name: str):
        if not self.current_program_data or not track_metadata_name: return
        program_tracks = self._get_program_tracks_list()
        new_play_order = len(program_tracks)
        new_track_entry = {
            "track_name": track_metadata_name, "play_order": new_play_order,
            "user_start_time_ms": 0, "user_end_time_ms": None
        }
        program_tracks.append(new_track_entry)
        self.populate_tracks_table(select_row=new_play_order)
        self.program_tracks_updated.emit()

    def remove_selected_track_from_program(self):
        selected_row = self.get_selected_row()
        if selected_row == -1 or not self.current_program_data: return
        program_tracks = self._get_program_tracks_list()
        if not (0 <= selected_row < len(program_tracks)): return

        del program_tracks[selected_row]
        for i, track_entry in enumerate(program_tracks):
            track_entry["play_order"] = i

        new_row_count = len(program_tracks)
        select_index = min(selected_row, new_row_count - 1) if new_row_count > 0 else -1
        self.populate_tracks_table(select_row=select_index)
        self.program_tracks_updated.emit()

    def get_selected_row(self):
        return self.tracks_table_widget.currentRow()

    def get_current_track_count(self):
        return len(self._get_program_tracks_list())