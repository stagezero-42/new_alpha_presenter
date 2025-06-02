# myapp/gui/audio_program_editor_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QSplitter, QLabel, QGroupBox, QTableWidget,
    QSpinBox, QCheckBox, QFormLayout, QInputDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from ..audio.audio_program_manager import AudioProgramManager
from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_icon_file_path  # get_media_file_path is used by player panel
from .widget_helpers import create_button
# Removed: is_safe_filename_component (handled by list panel or program_manager)
# Removed: QMediaPlayer, QAudioOutput, QUrl (now in player panel)
# Removed: QListWidget, QInputDialog (now in list panel or handled differently)
# Removed: QPushButton, QSlider (now in player panel)

from .audio_program_list_panel import AudioProgramListPanel  # New Import
from .audio_track_player_panel import AudioTrackPlayerPanel  # New Import
from .audio_track_in_program_manager import AudioTrackInProgramManager
from .audio_import_dialog import AudioImportDialog

logger = logging.getLogger(__name__)


class AudioProgramEditorWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Initializing AudioProgramEditorWindow...")
        self.setWindowTitle("Audio Program Editor [*]")
        self.setGeometry(200, 200, 1000, 750)  # Adjusted for potentially more compact UI
        self.setWindowModified(False)

        # Managers (passed to relevant components)
        self.program_manager = AudioProgramManager()
        self.track_manager = AudioTrackManager()

        self.programs_cache = {}  # Remains here to hold data for the *selected* program
        self.current_program_name = None  # Name of the currently selected program
        self._block_program_detail_signals = False  # For loop checkboxes etc.

        self._setup_ui()  # This will now instantiate panels

        # Manager for tracks table (this stays, as it's specific to the editor's table)
        self.track_in_program_manager = AudioTrackInProgramManager(self, self.tracks_table_widget)
        self.track_in_program_manager.program_tracks_updated.connect(self._handle_tracks_in_program_updated)
        # Connect selection in table to update the player panel
        self.tracks_table_widget.itemSelectionChanged.connect(self._handle_track_table_selection_changed)

        # Connect signals from panels
        self.program_list_panel.program_selected.connect(self._handle_program_selected_from_list_panel)
        self.program_list_panel.program_list_updated.connect(self._handle_program_list_changed_by_panel)
        self.track_player_panel.timing_update_requested.connect(self._handle_track_timing_update_from_player_panel)

        self._refresh_all_program_data_and_ui()  # Initial load and UI update
        logger.debug("AudioProgramEditorWindow initialized.")

    def _setup_ui(self):
        logger.debug("Setting up AudioProgramEditorWindow UI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_toolbar_layout = QHBoxLayout()
        top_toolbar_layout.addStretch()
        self.save_all_button = create_button("Save All Changes", "save.png", "Save all modified audio programs",
                                             self.save_all_changes)
        self.done_button = create_button("Done", "done.png", "Close this editor", self.close)
        top_toolbar_layout.addWidget(self.save_all_button)
        top_toolbar_layout.addWidget(self.done_button)
        main_layout.addLayout(top_toolbar_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Program List
        self.program_list_panel = AudioProgramListPanel(self.program_manager, self)
        splitter.addWidget(self.program_list_panel)

        # Right Panel: Program Details, Tracks Table, Track Controls, Player
        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)

        # Program Settings Group
        self.program_details_group = QGroupBox("Program Settings")
        program_details_form = QFormLayout(self.program_details_group)
        self.program_name_label = QLabel("Program: (None)")  # Just a label now
        self.program_name_label.setStyleSheet("font-weight: bold;")
        program_details_form.addRow(self.program_name_label)
        self.loop_indef_checkbox = QCheckBox("Loop Program Indefinitely")
        self.loop_indef_checkbox.toggled.connect(self._on_loop_setting_changed)
        program_details_form.addRow(self.loop_indef_checkbox)
        self.loop_count_spinbox = QSpinBox()
        self.loop_count_spinbox.setRange(0, 999)
        self.loop_count_spinbox.setToolTip("Number of times to loop (if not indefinite). 0 for no specific count.")
        self.loop_count_spinbox.valueChanged.connect(self._on_loop_setting_changed)
        program_details_form.addRow("Loop Count:", self.loop_count_spinbox)
        right_panel_layout.addWidget(self.program_details_group)

        # Tracks in Program Group
        self.tracks_group = QGroupBox("Audio Tracks in Program (Drag Row Header to Reorder)")
        tracks_layout = QVBoxLayout(self.tracks_group)
        self.tracks_table_widget = QTableWidget()  # Created here, passed to AudioTrackInProgramManager
        tracks_layout.addWidget(self.tracks_table_widget)
        tracks_buttons_layout = QHBoxLayout()
        self.add_track_to_program_button = create_button("Add Track Ref", "add.png",
                                                         "Add existing audio track metadata to program",
                                                         self.add_track_to_program_dialog)
        self.import_new_audio_button = create_button("Import New Audio File...", "import.png",
                                                     "Import new audio file and create metadata",
                                                     self.import_new_audio_file_dialog)
        self.remove_track_from_program_button = create_button("Remove From Program", "remove.png",
                                                              "Remove selected track from this program",
                                                              self.remove_selected_track_from_program_list)
        tracks_buttons_layout.addWidget(self.add_track_to_program_button)
        tracks_buttons_layout.addWidget(self.import_new_audio_button)
        tracks_buttons_layout.addWidget(self.remove_track_from_program_button)
        tracks_buttons_layout.addStretch()
        tracks_layout.addLayout(tracks_buttons_layout)
        right_panel_layout.addWidget(self.tracks_group)

        # Track Player Panel
        self.track_player_panel = AudioTrackPlayerPanel(self.track_manager, self)
        right_panel_layout.addWidget(self.track_player_panel)

        splitter.addWidget(right_panel_widget)
        splitter.setSizes([250, 750])  # Adjust as needed
        main_layout.addWidget(splitter)

        self._set_window_icon()
        logger.debug("AudioProgramEditorWindow UI setup complete.")

    def _set_window_icon(self):
        try:
            icon_path = get_icon_file_path("audio_icon.png") or get_icon_file_path("edit.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set AudioProgramEditorWindow icon: {e}", exc_info=True)

    def mark_dirty(self, dirty=True):
        self.setWindowModified(dirty)
        self.update_ui_state()  # Update save button state etc.

    def _refresh_all_program_data_and_ui(self, select_program_name=None):
        """Refreshes program list and updates UI for the selection."""
        if not select_program_name and self.current_program_name:
            select_program_name = self.current_program_name  # Try to reselect current

        self.program_list_panel.load_and_list_programs(select_program_name)
        # The selection signal from program_list_panel will trigger _handle_program_selected_from_list_panel
        # which will then load details into the right panel.
        # If no program is selected (e.g. list empty), _handle_program_selected_from_list_panel(None) is called.
        self.update_ui_state()

    def _handle_program_selected_from_list_panel(self, program_name: str | None):
        logger.info(f"Program selected via list panel: {program_name}")
        self.track_player_panel.load_track_for_playback(None)  # Clear player for new program

        if not program_name:
            self.current_program_name = None
            self.programs_cache.clear()  # Or just clear the specific one if a more refined cache is needed
            self.track_in_program_manager.set_current_program(None, None)
            self.program_name_label.setText("Program: (None)")
            self._clear_program_details_ui()
            self.update_ui_state()
            return

        if program_name == self.current_program_name and program_name in self.programs_cache:
            # Already selected and cached, ensure UI is consistent (e.g. if re-selected)
            program_data = self.programs_cache[program_name]
            self.track_in_program_manager.set_current_program(program_name, program_data)
            self._load_program_details_to_ui(program_data)
            self.update_ui_state()
            return

        self.current_program_name = program_name
        try:
            program_data = self.program_manager.load_program(program_name)
            self.programs_cache[program_name] = program_data  # Cache it

            self.track_in_program_manager.set_current_program(program_name, program_data)
            self.program_name_label.setText(f"Program: {program_name}")
            self._load_program_details_to_ui(program_data)

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load program '{program_name}': {e}")
            self.programs_cache.pop(program_name, None)
            self.current_program_name = None
            # Ask list panel to clear its selection or select first if any
            self.program_list_panel.select_program(None)
            # This will re-trigger _handle_program_selected_from_list_panel(None)

        self.update_ui_state()

    def _handle_program_list_changed_by_panel(self):
        """Called when panel signals add/rename/delete. Mark window dirty if not already."""
        # The panel itself calls load_and_list_programs.
        # We might need to update our cache or re-sync if names changed.
        # For simplicity now, we assume the panel's selection signal handles new state.
        # If a program was renamed or deleted, our cache might be stale for that item.
        # The `program_selected` signal from the list panel should give us the new current state.
        self.mark_dirty(True)  # Action in panel implies a change.

        # Clear stale cache entries if a program was deleted or renamed
        # A robust way is to rebuild cache based on current program_manager.list_programs()
        # Or, the list_panel could emit (old_name, new_name) for rename, and (deleted_name) for delete.
        # For now, selection change handles loading the current one. If the current one was deleted,
        # selection changes to None or another program.

    def _load_program_details_to_ui(self, program_data):
        if not program_data:
            self._clear_program_details_ui();
            return
        self._block_program_detail_signals = True
        self.loop_indef_checkbox.setChecked(program_data.get("loop_indefinitely", False))
        self.loop_count_spinbox.setValue(program_data.get("loop_count", 0))
        self.loop_count_spinbox.setEnabled(not self.loop_indef_checkbox.isChecked())
        self._block_program_detail_signals = False

    def _clear_program_details_ui(self):
        self._block_program_detail_signals = True
        self.program_name_label.setText("Program: (None)")
        self.loop_indef_checkbox.setChecked(False)
        self.loop_count_spinbox.setValue(0)
        self.loop_count_spinbox.setEnabled(True)  # Enable by default when no program
        self._block_program_detail_signals = False

    def _on_loop_setting_changed(self):
        if self._block_program_detail_signals or not self.current_program_name or \
                self.current_program_name not in self.programs_cache:
            return

        program_data = self.programs_cache[self.current_program_name]
        is_loop_indef = self.loop_indef_checkbox.isChecked()
        program_data["loop_indefinitely"] = is_loop_indef
        program_data["loop_count"] = self.loop_count_spinbox.value() if not is_loop_indef else 0
        self.loop_count_spinbox.setEnabled(not is_loop_indef)
        self.mark_dirty(True)

    def _handle_tracks_in_program_updated(self):
        """Called when AudioTrackInProgramManager signals a change."""
        self.mark_dirty(True)
        # If the current program's tracks array in the cache needs explicit update:
        if self.current_program_name and self.current_program_name in self.programs_cache and \
                self.track_in_program_manager.current_program_data:
            self.programs_cache[self.current_program_name]["tracks"] = \
                self.track_in_program_manager.current_program_data.get("tracks", [])

    def _handle_track_table_selection_changed(self):
        """When selection in the tracks table changes, update the player panel."""
        selected_row = self.track_in_program_manager.get_selected_row()
        if selected_row != -1 and self.track_in_program_manager.current_program_data:
            program_tracks = self.track_in_program_manager._get_program_tracks_list()
            if 0 <= selected_row < len(program_tracks):
                track_entry_data = program_tracks[selected_row]
                self.track_player_panel.load_track_for_playback(track_entry_data)
                return
        self.track_player_panel.load_track_for_playback(None)  # Clear player if no valid selection

    def _handle_track_timing_update_from_player_panel(self, start_ms, end_ms_or_none):
        """Player panel requests to update timing for the selected track in the table."""
        selected_row_in_table = self.track_in_program_manager.get_selected_row()
        if selected_row_in_table == -1 or not self.track_in_program_manager.current_program_data:
            logger.warning("Track timing update requested, but no track selected in table.")
            return

        program_tracks = self.track_in_program_manager._get_program_tracks_list()
        if 0 <= selected_row_in_table < len(program_tracks):
            track_entry = program_tracks[selected_row_in_table]

            # Validate before setting
            detected_duration_ms = self.track_player_panel.current_track_duration_ms_from_player

            valid_start = True
            if detected_duration_ms > 0 and start_ms >= detected_duration_ms:
                QMessageBox.warning(self, "Invalid Time", "Start time cannot be at or after the track's detected end.")
                valid_start = False

            valid_end = True
            if end_ms_or_none is not None:
                if end_ms_or_none < start_ms:
                    QMessageBox.warning(self, "Invalid End Time", "End time cannot be before start time.")
                    valid_end = False
                elif detected_duration_ms > 0 and end_ms_or_none > detected_duration_ms:
                    QMessageBox.warning(self, "Invalid End Time",
                                        f"End time cannot be after the track's detected end ({self.track_player_panel._format_ms_time(detected_duration_ms)}).")
                    valid_end = False

            if valid_start:
                track_entry["user_start_time_ms"] = start_ms
            if valid_end:  # This will be true if end_ms_or_none is None (clearing custom end)
                track_entry["user_end_time_ms"] = end_ms_or_none

            if valid_start or valid_end:  # if any change was made
                self.track_in_program_manager.populate_tracks_table(
                    select_row=selected_row_in_table)  # Refresh table cell widgets
                self.mark_dirty(True)
        else:
            logger.warning("Selected row for timing update is out of bounds.")

    def save_all_changes(self):
        logger.info("Saving all audio program changes...")
        if not self.isWindowModified():
            QMessageBox.information(self, "No Changes", "No changes to save.");
            return

        # Ensure current program details (looping) are in cache before iterating
        if self.current_program_name and self.current_program_name in self.programs_cache:
            current_program_data = self.programs_cache[self.current_program_name]
            current_program_data["loop_indefinitely"] = self.loop_indef_checkbox.isChecked()
            current_program_data["loop_count"] = self.loop_count_spinbox.value() if not current_program_data[
                "loop_indefinitely"] else 0
            # Tracks for current program are already updated in cache by _handle_tracks_in_program_updated

        saved_count, failed_count = 0, 0
        for name, data in self.programs_cache.items():
            if data:  # Ensure data exists (it should if it's in cache from loading/creating)
                try:
                    if data.get("program_name") != name:  # Ensure internal name matches filename key
                        logger.warning(f"Correcting internal program name for '{name}' to match key before saving.")
                        data["program_name"] = name
                    if self.program_manager.save_program(name, data):
                        saved_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error saving audio program '{name}': {e}", exc_info=True)
                    failed_count += 1

        if failed_count > 0: QMessageBox.warning(self, "Save Error",
                                                 f"Failed to save {failed_count} program(s). Check logs.")
        if saved_count > 0: QMessageBox.information(self, "Save Complete",
                                                    f"Successfully saved {saved_count} program(s).")

        if failed_count == 0:  # Only mark as not dirty if all saves succeeded
            self.mark_dirty(False)

    def import_new_audio_file_dialog(self):
        import_audio_dialog = AudioImportDialog(self, self.track_manager)
        # We might want to refresh available tracks for 'Add Track Ref' if import is successful.
        # For now, user has to re-open 'Add Track Ref' to see new track.
        import_audio_dialog.exec()

    def add_track_to_program_dialog(self):
        if not self.current_program_name:
            QMessageBox.warning(self, "No Program Selected", "Please select or create an audio program first.");
            return

        available_track_metadata_names = sorted(self.track_manager.list_audio_tracks())
        if not available_track_metadata_names:
            QMessageBox.information(self, "No Audio Tracks",
                                    "No audio track metadata found. Please import audio files first.");
            return

        track_name, ok = QInputDialog.getItem(self, "Add Audio Track to Program", "Select Track Metadata:",
                                              available_track_metadata_names, 0, False)
        if ok and track_name:
            self.track_in_program_manager.add_track_to_program(track_name)
            # _handle_tracks_in_program_updated will be called via signal, marking dirty

    def remove_selected_track_from_program_list(self):
        if not self.current_program_name:
            QMessageBox.warning(self, "No Program Selected", "Select a program first.");
            return
        self.track_in_program_manager.remove_selected_track_from_program()
        # _handle_tracks_in_program_updated will be called

    def update_ui_state(self):
        program_is_selected = self.current_program_name is not None

        self.program_details_group.setEnabled(program_is_selected)
        self.tracks_group.setEnabled(program_is_selected)
        # Player panel manages its own internal state via its update_controls_state
        self.track_player_panel.setEnabled(
            program_is_selected and self.track_in_program_manager.get_selected_row() != -1)

        track_selected_in_table = False
        if program_is_selected and self.track_in_program_manager:
            track_selected_in_table = self.track_in_program_manager.get_selected_row() != -1

        self.add_track_to_program_button.setEnabled(program_is_selected)
        # import_new_audio_button is always enabled as it's a global action
        self.remove_track_from_program_button.setEnabled(track_selected_in_table)

        self.save_all_button.setEnabled(self.isWindowModified())

    def closeEvent(self, event):
        logger.debug("AudioProgramEditorWindow closeEvent triggered.")
        self.track_player_panel._stop_playback(internal_call=True)  # Ensure player is stopped

        if self.isWindowModified():
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "There are unsaved changes in the audio programs.\nSave them now?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Save)
            if reply == QMessageBox.StandardButton.Save:
                self.save_all_changes()
                if self.isWindowModified():  # If save failed or didn't clear dirty flag
                    event.ignore();
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore();
                return

        event.accept()
        if event.isAccepted(): logger.info("AudioProgramEditorWindow closing.")