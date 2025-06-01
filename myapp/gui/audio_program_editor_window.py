# myapp/gui/audio_program_editor_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QMessageBox, QInputDialog,
    QSplitter, QLabel, QGroupBox, QTableWidget,
    QPushButton, QSlider, QSpinBox, QCheckBox,
    QFormLayout  # Ensuring this import is present
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..audio.audio_program_manager import AudioProgramManager
from ..audio.audio_track_manager import AudioTrackManager
from ..utils.paths import get_icon_file_path, get_media_file_path
from .widget_helpers import create_button
from ..utils.security import is_safe_filename_component
from .audio_track_in_program_manager import AudioTrackInProgramManager
from .audio_import_dialog import AudioImportDialog

logger = logging.getLogger(__name__)


class AudioProgramEditorWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Initializing AudioProgramEditorWindow...")
        self.setWindowTitle("Audio Program Editor [*]")
        self.setGeometry(200, 200, 1000, 750)
        self.setWindowModified(False)

        self.program_manager = AudioProgramManager()
        self.track_manager = AudioTrackManager()
        self.programs_cache = {}
        self.current_program_name = None
        self._block_list_signals = False  # Used for program list widget

        # MediaPlayer and AudioOutput Setup
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        # self.audio_output.setVolume(0.8) # Example: Set volume 0.0 to 1.0

        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)
        self.media_player.mediaStatusChanged.connect(self._on_player_media_status_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)

        self.current_loaded_track_for_player = None  # Stores metadata of track in player
        self.current_track_duration_ms = 0

        self._setup_ui()  # This is the call that was failing

        # Manager for tracks within the selected program
        # self.tracks_table_widget is created in _setup_track_editor_panel, called by _setup_ui
        self.track_in_program_manager = AudioTrackInProgramManager(self, self.tracks_table_widget)
        self.track_in_program_manager.program_tracks_updated.connect(lambda: self.mark_dirty(True))

        self.load_and_list_programs()
        self.update_ui_state()
        logger.debug("AudioProgramEditorWindow initialized.")

    def _setup_ui(self):  # <<< DEFINITION OF THE METHOD
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
        self._setup_program_panel(splitter)  # Creates program list UI
        self._setup_track_editor_panel(splitter)  # Creates track editing UI (including self.tracks_table_widget)

        splitter.setSizes([250, 750])
        main_layout.addWidget(splitter)

        try:
            icon_path = get_icon_file_path("audio_icon.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                fallback_icon_path = get_icon_file_path("edit.png")
                if fallback_icon_path and os.path.exists(fallback_icon_path):
                    self.setWindowIcon(QIcon(fallback_icon_path))
        except Exception as e:
            logger.error(f"Failed to set AudioProgramEditorWindow icon: {e}", exc_info=True)
        logger.debug("AudioProgramEditorWindow UI setup complete.")

    def _setup_program_panel(self, splitter):
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Audio Programs:"))

        self.program_list_widget = QListWidget()
        self.program_list_widget.currentItemChanged.connect(self.handle_program_selection_changed)
        left_layout.addWidget(self.program_list_widget)

        program_buttons_layout = QHBoxLayout()
        self.add_program_button = create_button("Add", "add.png", "Add New Program", self.add_program)
        self.rename_program_button = create_button("Rename", "edit.png", "Rename Selected Program", self.rename_program)
        self.del_program_button = create_button("Delete", "remove.png", "Delete Selected Program", self.delete_program)
        program_buttons_layout.addWidget(self.add_program_button)
        program_buttons_layout.addWidget(self.rename_program_button)
        program_buttons_layout.addWidget(self.del_program_button)
        left_layout.addLayout(program_buttons_layout)
        splitter.addWidget(left_widget)

    def _setup_track_editor_panel(self, splitter):
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.program_details_group = QGroupBox("Program Settings")
        # QFormLayout is used here
        program_details_form = QFormLayout(self.program_details_group)
        self.program_name_label = QLabel("Program: (None)")
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
        right_layout.addWidget(self.program_details_group)

        self.tracks_group = QGroupBox("Audio Tracks in Program (Drag Row Header to Reorder)")
        tracks_layout = QVBoxLayout(self.tracks_group)

        self.tracks_table_widget = QTableWidget()  # Instance created here
        tracks_layout.addWidget(self.tracks_table_widget)

        tracks_buttons_layout = QHBoxLayout()
        self.add_track_button = create_button("Add Track", "add.png", "Add existing audio track to program",
                                              self.add_track_to_program)
        self.import_new_audio_button = create_button("Import New Audio File...", "import.png",
                                                     "Import new audio file into system & create track metadata",
                                                     self.import_new_audio_file)
        self.remove_track_button = create_button("Remove Track", "remove.png", "Remove selected track from program",
                                                 self.remove_track_from_program)
        tracks_buttons_layout.addWidget(self.add_track_button)
        tracks_buttons_layout.addWidget(self.import_new_audio_button)
        tracks_buttons_layout.addWidget(self.remove_track_button)
        tracks_buttons_layout.addStretch()
        tracks_layout.addLayout(tracks_buttons_layout)
        right_layout.addWidget(self.tracks_group)

        self._setup_playback_tools(right_layout)
        splitter.addWidget(right_widget)

    def _setup_playback_tools(self, parent_layout):
        self.playback_tools_group = QGroupBox("Track Playback & Timing Tool")
        playback_layout = QVBoxLayout(self.playback_tools_group)

        self.loaded_track_label = QLabel("Loaded for Playback: None")
        playback_layout.addWidget(self.loaded_track_label)

        self.playback_slider = QSlider(Qt.Orientation.Horizontal)
        self.playback_slider.setRange(0, 1000)
        self.playback_slider.sliderMoved.connect(self.media_player.setPosition)
        self.playback_slider.setEnabled(False)
        playback_layout.addWidget(self.playback_slider)

        time_layout = QHBoxLayout()
        self.current_pos_label = QLabel("00:00.000")
        self.total_duration_label = QLabel("/ 00:00.000")
        time_layout.addWidget(self.current_pos_label)
        time_layout.addStretch()
        time_layout.addWidget(self.total_duration_label)
        playback_layout.addLayout(time_layout)

        controls_layout = QHBoxLayout()
        self.play_button = create_button("", "play.png", "Play/Pause", self._toggle_play_pause)
        self.stop_button = create_button("", "stop.png", "Stop", self._stop_playback)
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addStretch()

        self.set_start_button = create_button("Set Start", on_click=self._set_current_pos_as_start)
        self.set_end_button = create_button("Set End", on_click=self._set_current_pos_as_end)
        self.set_start_button.setEnabled(False)
        self.set_end_button.setEnabled(False)
        controls_layout.addWidget(self.set_start_button)
        controls_layout.addWidget(self.set_end_button)
        playback_layout.addLayout(controls_layout)

        parent_layout.addWidget(self.playback_tools_group)

    def mark_dirty(self, dirty=True):
        self.setWindowModified(dirty)
        self.update_ui_state()

    def load_and_list_programs(self):
        logger.debug("Loading and listing audio programs...")
        current_selection_name = self.current_program_name

        self._block_list_signals = True
        self.program_list_widget.clear()
        self._block_list_signals = False

        try:
            program_names = sorted(self.program_manager.list_programs())
            if not program_names:
                self.current_program_name = None
                if self.track_in_program_manager: self.track_in_program_manager.set_current_program(None, None)
                self.program_name_label.setText("Program: (None)")
                self._clear_program_details_ui()
                self.update_ui_state()
                return

            self.program_list_widget.addItems(program_names)
            restored_selection = False
            if current_selection_name and current_selection_name in program_names:
                for i in range(self.program_list_widget.count()):
                    if self.program_list_widget.item(i).text() == current_selection_name:
                        self.program_list_widget.setCurrentRow(i)
                        restored_selection = True
                        break

            if not restored_selection and self.program_list_widget.count() > 0:
                self.program_list_widget.setCurrentRow(0)

            if self.program_list_widget.count() == 0 or not self.program_list_widget.currentItem():
                self.handle_program_selection_changed(None, None)

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to list audio programs: {e}")
            self.current_program_name = None
            if self.track_in_program_manager: self.track_in_program_manager.set_current_program(None, None)
            self.program_name_label.setText("Program: (None)")
            self._clear_program_details_ui()
        self.update_ui_state()

    def handle_program_selection_changed(self, current_item, previous_item):
        if self._block_list_signals: return

        if not current_item:
            self.current_program_name = None
            if self.track_in_program_manager: self.track_in_program_manager.set_current_program(None, None)
            self.program_name_label.setText("Program: (None)")
            self._clear_program_details_ui()
            self.update_audio_player_ui_for_track(None)
            self.update_ui_state()
            return

        selected_program_name = current_item.text()
        if selected_program_name == self.current_program_name and self.current_program_name in self.programs_cache:
            program_data = self.programs_cache[self.current_program_name]
            if self.track_in_program_manager:
                self.track_in_program_manager.set_current_program(self.current_program_name, program_data)
            self._load_program_details_to_ui(program_data)
            self.update_ui_state()
            return

        self.current_program_name = selected_program_name
        logger.info(f"Audio program selected: {self.current_program_name}")

        if self.current_program_name not in self.programs_cache:
            try:
                self.programs_cache[self.current_program_name] = \
                    self.program_manager.load_program(self.current_program_name)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load program '{self.current_program_name}': {e}")
                self.programs_cache.pop(self.current_program_name, None)

                # Properly deselect if load failed
                self._block_list_signals = True  # Prevent re-triggering if setCurrentItem(None) is called
                if self.program_list_widget.currentItem() and self.program_list_widget.currentItem().text() == self.current_program_name:
                    self.program_list_widget.setCurrentItem(None)  # Deselect from UI
                self._block_list_signals = False

                self.current_program_name = None  # Clear internal state
                if self.track_in_program_manager: self.track_in_program_manager.set_current_program(None, None)
                self.program_name_label.setText("Program: (None)")
                self._clear_program_details_ui()
                self.update_audio_player_ui_for_track(None)
                self.update_ui_state()
                return

        program_data = self.programs_cache.get(self.current_program_name)
        if program_data:
            if self.track_in_program_manager: self.track_in_program_manager.set_current_program(
                self.current_program_name, program_data)
            self.program_name_label.setText(f"Program: {self.current_program_name}")
            self._load_program_details_to_ui(program_data)
        else:
            if self.track_in_program_manager: self.track_in_program_manager.set_current_program(None, None)
            self.program_name_label.setText("Program: (None)")
            self._clear_program_details_ui()
            self.update_audio_player_ui_for_track(None)

        self.update_ui_state()

    def _load_program_details_to_ui(self, program_data):
        if not program_data:
            self._clear_program_details_ui()
            return
        self._block_list_signals = True
        self.loop_indef_checkbox.setChecked(program_data.get("loop_indefinitely", False))
        self.loop_count_spinbox.setValue(program_data.get("loop_count", 0))
        self.loop_count_spinbox.setEnabled(not self.loop_indef_checkbox.isChecked())
        self._block_list_signals = False

    def _clear_program_details_ui(self):
        self._block_list_signals = True
        self.loop_indef_checkbox.setChecked(False)
        self.loop_count_spinbox.setValue(0)
        self.loop_count_spinbox.setEnabled(True)
        self._block_list_signals = False

    def _on_loop_setting_changed(self):
        if self._block_list_signals or not self.current_program_name or not self.current_program_name in self.programs_cache:
            return

        program_data = self.programs_cache[self.current_program_name]
        is_loop_indef = self.loop_indef_checkbox.isChecked()
        program_data["loop_indefinitely"] = is_loop_indef
        program_data["loop_count"] = self.loop_count_spinbox.value() if not is_loop_indef else 0

        self.loop_count_spinbox.setEnabled(not is_loop_indef)
        self.mark_dirty(True)

    def add_program(self):
        program_name, ok = QInputDialog.getText(self, "New Audio Program", "Enter name for the new program:")
        if ok and program_name:
            safe_name = program_name.strip().replace(" ", "_")
            if not is_safe_filename_component(f"{safe_name}.json"):
                QMessageBox.warning(self, "Invalid Name", "Name contains invalid characters or is reserved.");
                return
            if safe_name in self.program_manager.list_programs():
                QMessageBox.warning(self, "Name Exists", "A program with this name already exists.");
                return

            new_program_data = {"program_name": safe_name, "tracks": [], "loop_indefinitely": False, "loop_count": 0}
            if self.program_manager.save_program(safe_name, new_program_data):
                self.programs_cache[safe_name] = new_program_data
                self._refresh_and_select_program(safe_name)
            else:
                QMessageBox.critical(self, "Save Error", "Could not save the new audio program.")

    def rename_program(self):
        if not self.current_program_name: return
        old_name = self.current_program_name
        new_name_input, ok = QInputDialog.getText(self, "Rename Program", f"New name for '{old_name}':", text=old_name)
        if not (ok and new_name_input and new_name_input.strip()): return

        safe_new_name = new_name_input.strip().replace(" ", "_")
        if safe_new_name == old_name: return
        if not is_safe_filename_component(f"{safe_new_name}.json"):
            QMessageBox.warning(self, "Invalid Name", "New name contains invalid characters or is reserved.");
            return

        existing_program_names_lower = [name.lower() for name in self.program_manager.list_programs()]
        if safe_new_name.lower() in existing_program_names_lower and safe_new_name.lower() != old_name.lower():
            QMessageBox.warning(self, "Name Exists", "A program with the new name already exists.");
            return

        current_data = self.programs_cache.get(old_name)
        if not current_data:
            try:
                current_data = self.program_manager.load_program(old_name)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Could not load program '{old_name}' for rename: {e}"); return

        current_data["program_name"] = safe_new_name
        if self.program_manager.save_program(safe_new_name, current_data):
            if old_name.lower() != safe_new_name.lower():
                self.program_manager.delete_program(old_name)

            if old_name in self.programs_cache: del self.programs_cache[old_name]
            self.programs_cache[safe_new_name] = current_data
            self.current_program_name = safe_new_name
            self._refresh_and_select_program(safe_new_name)
        else:
            current_data["program_name"] = old_name
            QMessageBox.critical(self, "Save Error", "Could not save program with the new name.")

    def delete_program(self):
        if not self.current_program_name: return
        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete the audio program '{self.current_program_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.program_manager.delete_program(self.current_program_name):
                if self.current_program_name in self.programs_cache:
                    del self.programs_cache[self.current_program_name]
                self.current_program_name = None
                self._refresh_and_select_program(None)
            else:
                QMessageBox.critical(self, "Delete Error", "Could not delete the program file.")

    def _refresh_and_select_program(self, program_name_to_select):
        old_selection = program_name_to_select if program_name_to_select else self.current_program_name
        self.load_and_list_programs()

        selected_idx = -1
        if old_selection:
            for i in range(self.program_list_widget.count()):
                if self.program_list_widget.item(i).text() == old_selection:
                    selected_idx = i
                    break
        elif self.program_list_widget.count() > 0:
            selected_idx = 0

        if selected_idx != -1:
            self.program_list_widget.setCurrentRow(selected_idx)
        else:  # If old selection no longer exists or list is empty
            self.handle_program_selection_changed(None, None)  # Explicitly handle deselection

        self.mark_dirty(False)

    def save_all_changes(self):
        logger.info("Saving all audio program changes...")
        if not self.isWindowModified():
            return

        if self.current_program_name and self.current_program_name in self.programs_cache:
            program_data = self.programs_cache[self.current_program_name]
            program_data["loop_indefinitely"] = self.loop_indef_checkbox.isChecked()
            program_data["loop_count"] = self.loop_count_spinbox.value() if not program_data["loop_indefinitely"] else 0

        saved_count, failed_count = 0, 0
        for name, data in self.programs_cache.items():
            if data:
                try:
                    if data.get("program_name") != name: data["program_name"] = name
                    if self.program_manager.save_program(name, data):
                        saved_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error saving audio program '{name}': {e}", exc_info=True);
                    failed_count += 1

        if failed_count > 0: QMessageBox.warning(self, "Save Error",
                                                 f"Failed to save {failed_count} program(s). Check logs.")
        if saved_count > 0 and failed_count == 0: QMessageBox.information(self, "Save Complete",
                                                                          f"Successfully saved {saved_count} program(s).")

        if failed_count == 0: self.mark_dirty(False)

    def import_new_audio_file(self):
        import_audio_dialog = AudioImportDialog(self, self.track_manager)
        import_audio_dialog.exec()

    def add_track_to_program(self):
        if not self.current_program_name:
            QMessageBox.warning(self, "No Program Selected", "Please select or create an audio program first.");
            return

        available_track_metadata_names = sorted(self.track_manager.list_audio_tracks())
        if not available_track_metadata_names:
            QMessageBox.information(self, "No Audio Tracks",
                                    "No audio track metadata found. Please import audio files first using 'Import New Audio File...'.")
            return

        track_name, ok = QInputDialog.getItem(self, "Add Audio Track to Program",
                                              "Select Track Metadata:",
                                              available_track_metadata_names, 0, False)
        if ok and track_name:
            self.track_in_program_manager.add_track_to_program(track_name)

    def remove_track_from_program(self):
        if not self.current_program_name:
            QMessageBox.warning(self, "No Program Selected", "Select a program first.");
            return
        self.track_in_program_manager.remove_selected_track_from_program()

    def update_ui_state(self):
        program_selected = self.current_program_name is not None
        # ... (other UI element states) ...
        self.rename_program_button.setEnabled(program_selected)
        self.del_program_button.setEnabled(program_selected)
        self.program_details_group.setEnabled(program_selected)
        self.tracks_group.setEnabled(program_selected)

        track_selected_in_table = False
        if program_selected and self.track_in_program_manager:
            track_selected_in_table = self.track_in_program_manager.get_selected_row() != -1

        self.add_track_button.setEnabled(program_selected)
        self.remove_track_button.setEnabled(track_selected_in_table)

        # Determine if player controls should be active
        player_is_ready_for_interaction = False
        if track_selected_in_table and self.current_loaded_track_for_player:
            status = self.media_player.mediaStatus()
            # Ready if loaded, buffered, or even buffering (as user might want to pause/stop a buffer attempt)
            if status in [QMediaPlayer.MediaStatus.LoadedMedia,
                          QMediaPlayer.MediaStatus.BufferedMedia,
                          QMediaPlayer.MediaStatus.BufferingMedia,
                          QMediaPlayer.MediaStatus.EndOfMedia]:  # EndOfMedia is also a valid state to interact from (e.g. replay)
                player_is_ready_for_interaction = True
            # Allow stop even if loading or stalled
            if status in [QMediaPlayer.MediaStatus.LoadingMedia, QMediaPlayer.MediaStatus.StalledMedia]:
                self.stop_button.setEnabled(True)

        self.playback_tools_group.setEnabled(track_selected_in_table)
        self.play_button.setEnabled(player_is_ready_for_interaction)
        # Stop button should be enabled if playing, paused, or even if just loaded and ready to be played (then stopped)
        self.stop_button.setEnabled(
            player_is_ready_for_interaction and self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState or \
            (
                        player_is_ready_for_interaction and self.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState and self.media_player.position() > 0))

        self.playback_slider.setEnabled(player_is_ready_for_interaction and self.current_track_duration_ms > 0)
        self.set_start_button.setEnabled(player_is_ready_for_interaction)
        self.set_end_button.setEnabled(player_is_ready_for_interaction)

        self.save_all_button.setEnabled(self.isWindowModified())
        self._update_player_button_icon()  # Ensure icon is correct based on playback state

    def update_audio_player_ui_for_track(self, track_entry_data_in_program):
        logger.info(
            f"Updating player UI for track entry: {track_entry_data_in_program.get('track_name') if track_entry_data_in_program else 'None'}")
        self.media_player.stop()  # Stop any current playback before changing source
        self._update_player_button_icon()
        self.current_loaded_track_for_player = None
        self.current_track_duration_ms = 0
        self.playback_slider.setValue(0)
        self.playback_slider.setEnabled(False)
        self.loaded_track_label.setText("Loaded for Playback: None")
        self.current_pos_label.setText(self._format_ms_time(0))
        self.total_duration_label.setText(f"/ {self._format_ms_time(0)}")

        if track_entry_data_in_program:
            track_metadata_name = track_entry_data_in_program.get("track_name")
            logger.debug(f"Attempting to load metadata for track: {track_metadata_name}")
            try:
                track_metadata = self.track_manager.load_track_metadata(track_metadata_name)
                if track_metadata and track_metadata.get("file_path"):
                    media_file_name = track_metadata["file_path"]
                    media_content_path = get_media_file_path(media_file_name)
                    logger.info(f"Attempting to set source for player: {media_content_path}")
                    if os.path.exists(media_content_path):
                        self.loaded_track_label.setText(f"Loading: {track_metadata_name}...")
                        self.media_player.setSource(QUrl.fromLocalFile(media_content_path))
                        self.current_loaded_track_for_player = track_metadata
                        # Actual readiness will be signaled by mediaStatusChanged -> LoadedMedia
                    else:
                        self.loaded_track_label.setText(f"Error: File not found - {media_file_name}")
                        logger.error(f"Audio file not found at expected path: {media_content_path}")
                else:
                    self.loaded_track_label.setText(f"Error: Metadata or file_path missing for {track_metadata_name}")
                    logger.warning(f"No file_path in metadata for track: {track_metadata_name}")
            except Exception as e:
                logger.error(f"Exception loading track metadata '{track_metadata_name}' for playback: {e}",
                             exc_info=True)
                self.loaded_track_label.setText(f"Error loading metadata: {track_metadata_name}")
        else:
            logger.debug("No track entry data provided, clearing player.")
            if not self.media_player.source().isEmpty():  # Clear source if one was set
                self.media_player.setSource(QUrl())

        self.update_ui_state()  # Update UI based on whether a track is (being) loaded

    def _format_ms_time(self, ms):
        if ms <= 0: return "00:00.000"
        tot_secs = ms / 1000.0
        minutes = int(tot_secs // 60)
        seconds = tot_secs % 60
        return f"{minutes:02d}:{seconds:06.3f}"

    def _on_player_position_changed(self, position_ms):
        if not self.playback_slider.isSliderDown():
            self.playback_slider.setValue(position_ms)
        self.current_pos_label.setText(self._format_ms_time(position_ms))

    def _on_player_duration_changed(self, duration_ms):
        logger.debug(f"Player duration changed: {duration_ms} ms")
        self.current_track_duration_ms = duration_ms if duration_ms > 0 else 0
        self.playback_slider.setRange(0,
                                      self.current_track_duration_ms if self.current_track_duration_ms > 0 else 1000)  # Avoid 0-0 range
        self.total_duration_label.setText(f"/ {self._format_ms_time(self.current_track_duration_ms)}")
        # Update UI state now that duration is known (or re-known)
        self.update_ui_state()

    def _on_player_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        track_name_for_log = self.current_loaded_track_for_player.get('track_name',
                                                                      'N/A') if self.current_loaded_track_for_player else "N/A"
        # Reduced verbosity for general status changes, but log key ones
        if status not in [QMediaPlayer.MediaStatus.BufferingMedia, QMediaPlayer.MediaStatus.BufferedMedia] or \
                status == QMediaPlayer.MediaStatus.LoadedMedia:  # Log important transitions
            logger.info(
                f"MediaStatusChanged for '{track_name_for_log}': {status}, PlaybackState: {self.media_player.playbackState()}, Position: {self.media_player.position()}ms, Duration: {self.media_player.duration()}ms")

        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.loaded_track_label.setText(f"Ready: {track_name_for_log}")
            logger.info(
                f"Media loaded for '{track_name_for_log}'. Duration: {self.media_player.duration()}ms. Issuing a proactive stop to prime player.")
            # *** NEW: Proactively stop the player once media is loaded ***
            # This ensures it's in a clean StoppedState with the new media.
            # The subsequent first 'play' command by the user will then act like the "second play"
            # which you observed works.
            self.media_player.stop()
            logger.info(
                f"Player stopped after LoadedMedia. New PlaybackState: {self.media_player.playbackState()}, Position: {self.media_player.position()}")
            # Duration should have been updated by durationChanged signal.
            # UI state update will enable play button etc.
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.info(f"EndOfMedia for '{track_name_for_log}'. Player will stop.")
            self._update_player_button_icon()  # Ensure play icon shows
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            logger.info(f"NoMedia status for player. Current track context: '{track_name_for_log}'")
            self.loaded_track_label.setText("Loaded for Playback: None")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.error(
                f"InvalidMedia status for source: {self.media_player.source().path()} (Track context: '{track_name_for_log}')")
            if self.current_loaded_track_for_player:
                QMessageBox.warning(self, "Playback Error",
                                    f"The audio file for '{track_name_for_log}' could not be played (invalid media).")
            self.loaded_track_label.setText(f"Error: Invalid media for {track_name_for_log}")
            self.current_loaded_track_for_player = None
        elif status == QMediaPlayer.MediaStatus.LoadingMedia:
            self.loaded_track_label.setText(f"Loading: {track_name_for_log}...")
        # Other statuses like Buffering, Buffered, Stalled, Unknown logged at the start of the method if needed.

        self.update_ui_state()  # Update UI based on the new state

    def _on_player_error(self, error_enum, error_string=""):
        logger.error(f"MediaPlayer Error Enum: {error_enum}, String: '{error_string}'")
        # QMediaPlayer.errorString() often gives more details than the passed error_string
        detailed_error_string = self.media_player.errorString()
        logger.error(f"MediaPlayer.errorString(): {detailed_error_string}")

        final_error_message = detailed_error_string if detailed_error_string else error_string
        if not final_error_message and error_enum != QMediaPlayer.Error.NoError:
            final_error_message = "Unknown QMediaPlayer error occurred."

        if error_enum != QMediaPlayer.Error.NoError:
            QMessageBox.warning(self, "Playback Error", f"Could not play audio: {final_error_message}")

        self.loaded_track_label.setText(
            f"Playback Error for: {self.current_loaded_track_for_player.get('track_name') if self.current_loaded_track_for_player else 'Unknown'}")
        if self.media_player.source().isValid() or not self.media_player.source().isEmpty():
            self.media_player.setSource(QUrl())  # Clear invalid or problematic source
        self.current_loaded_track_for_player = None
        self._update_player_button_icon()
        self.update_ui_state()

    def _update_player_button_icon(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(QIcon(get_icon_file_path("pause.png")))
            self.play_button.setToolTip("Pause")
        else:
            self.play_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.play_button.setToolTip("Play")

    def _toggle_play_pause(self):
        # Guard: Is there even a track context in the UI?
        if not self.current_loaded_track_for_player:
            QMessageBox.information(self, "No Track Loaded",
                                    "Please select a track from a program to load it for playback.")
            logger.warning("Play toggled, but no track context (self.current_loaded_track_for_player is None).")
            return

        # Guard: Does the player think it has a source?
        if self.media_player.source().isEmpty():
            logger.warning(
                "Play toggled, QMediaPlayer source is empty. Attempting to re-associate source via update_audio_player_ui_for_track.")
            # Try to get current selection from track manager and reload it
            selected_row = self.track_in_program_manager.get_selected_row()
            if selected_row != -1:
                program_tracks = self.track_in_program_manager._get_program_tracks_list()
                if 0 <= selected_row < len(program_tracks):
                    self.update_audio_player_ui_for_track(program_tracks[selected_row])
                    QMessageBox.information(self, "Source Reloaded",
                                            "Player source was empty. Re-loaded selected track. Please try playing again.")
                else:
                    QMessageBox.warning(self, "Playback Issue", "Could not find selected track data to reload source.")
            else:
                QMessageBox.information(self, "No Selection", "No track selected in table to reload and play.")
            return

        current_playback_state = self.media_player.playbackState()
        current_media_status = self.media_player.mediaStatus()
        current_position = self.media_player.position()
        track_name_for_log = self.current_loaded_track_for_player.get('track_name', 'N/A')

        logger.info(
            f"Toggle Play/Pause for '{track_name_for_log}': Current PlaybackState: {current_playback_state}, MediaStatus: {current_media_status}, Position: {current_position}ms")

        if current_media_status == QMediaPlayer.MediaStatus.InvalidMedia:
            QMessageBox.warning(self, "Invalid Media",
                                f"Cannot play '{track_name_for_log}': the media is marked as invalid.")
            return

        if current_playback_state == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            logger.info(f"Audio PAUSED for '{track_name_for_log}' at {self.media_player.position()}ms.")
        else:  # Was Paused or Stopped
            # If media is at the end, or stopped very near the start, explicitly set position to 0.
            # This helps ensure playback starts from the beginning for re-plays or problematic files.
            if current_media_status == QMediaPlayer.MediaStatus.EndOfMedia:
                logger.info(f"Track '{track_name_for_log}' was at EndOfMedia. Resetting position to 0 before playing.")
                if self.media_player.isSeekable():
                    self.media_player.setPosition(0)
                else:
                    logger.warning(f"Cannot seek '{track_name_for_log}' to reset from EndOfMedia, playback may fail.")
            elif current_playback_state == QMediaPlayer.PlaybackState.StoppedState and current_position < 50:  # If stopped at/near beginning
                logger.info(f"Track '{track_name_for_log}' is Stopped at/near position 0. Ensuring position 0.")
                if self.media_player.isSeekable() and current_position != 0:  # If not exactly 0, set it.
                    self.media_player.setPosition(0)

            # Check if media is in a state where playback can be reasonably attempted
            if current_media_status in [QMediaPlayer.MediaStatus.LoadedMedia,
                                        QMediaPlayer.MediaStatus.BufferedMedia,
                                        QMediaPlayer.MediaStatus.BufferingMedia,  # It might be buffering then play
                                        QMediaPlayer.MediaStatus.EndOfMedia]:  # After setPosition(0), should transition from EndOfMedia

                logger.info(
                    f"Attempting to PLAY '{track_name_for_log}'. Current PlaybackState: {self.media_player.playbackState()}, MediaStatus: {self.media_player.mediaStatus()}, Position: {self.media_player.position()}")
                self.media_player.play()
                # Logging after play() command to see immediate change or errors
                logger.info(
                    f"play() command issued for '{track_name_for_log}'. Resulting PlaybackState: {self.media_player.playbackState()}, MediaStatus: {self.media_player.mediaStatus()}, Error: {self.media_player.errorString()} ({self.media_player.error()})")

            elif current_media_status == QMediaPlayer.MediaStatus.LoadingMedia:
                QMessageBox.information(self, "Still Loading",
                                        f"Audio for '{track_name_for_log}' is still loading. Please wait.")
                logger.info("Play attempted while media status is LoadingMedia.")
            else:
                logger.warning(
                    f"Play attempted for '{track_name_for_log}' in an unexpected MediaStatus: {current_media_status}. Playback may not occur.")
                # Optionally try to play anyway if it's an unknown but not explicitly "bad" state.
                # self.media_player.play()

        self._update_player_button_icon()
        # UI state like button enablement will be driven by signals (playbackStateChanged, mediaStatusChanged)
        # calling update_ui_state().

    def _stop_playback(self):
        track_name_for_log = self.current_loaded_track_for_player.get('track_name',
                                                                      'N/A') if self.current_loaded_track_for_player else "N/A"
        logger.info(
            f"Stop playback requested for '{track_name_for_log}'. Current PlaybackState: {self.media_player.playbackState()}, Position: {self.media_player.position()}")

        self.media_player.stop()
        # QMediaPlayer.stop() is documented to set position to 0 and state to StoppedState.

        logger.info(
            f"Playback stopped for '{track_name_for_log}'. New PlaybackState: {self.media_player.playbackState()}, New Position: {self.media_player.position()}")

        self._update_player_button_icon()

        # Manually update slider and current position label as positionChanged(0) might not always
        # fire immediately or consistently across all backends when stop() is called.
        self.playback_slider.setValue(0)
        self.current_pos_label.setText(self._format_ms_time(0))

        self.update_ui_state()  # Refresh general UI state

    def _set_current_pos_as_start(self):
        selected_row = self.track_in_program_manager.get_selected_row()
        if selected_row == -1 or not self.track_in_program_manager.current_program_data: return

        program_tracks = self.track_in_program_manager._get_program_tracks_list()
        if 0 <= selected_row < len(program_tracks):
            current_pos_ms = self.media_player.position()
            track_entry = program_tracks[selected_row]

            detected_duration = self.current_track_duration_ms
            if detected_duration > 0 and current_pos_ms >= detected_duration:  # Start cannot be at or after full end
                QMessageBox.warning(self, "Invalid Time", "Start time cannot be at or after the track's detected end.")
                return

            track_entry["user_start_time_ms"] = current_pos_ms

            start_spin = self.track_in_program_manager.tracks_table_widget.cellWidget(selected_row,
                                                                                      AudioTrackInProgramManager.COL_START_TIME)
            if start_spin: start_spin.setValue(current_pos_ms)

            end_ms = track_entry.get("user_end_time_ms")
            if end_ms is not None and current_pos_ms > end_ms:  # If new start is after current custom end
                track_entry["user_end_time_ms"] = None  # Reset custom end time, play to actual end
                end_spin = self.track_in_program_manager.tracks_table_widget.cellWidget(selected_row,
                                                                                        AudioTrackInProgramManager.COL_END_TIME)
                if end_spin: end_spin.setValue(0)  # 0 for "Track End" in spinbox

            self.track_in_program_manager.program_tracks_updated.emit()
            QMessageBox.information(self, "Time Set", f"Start time set to {self._format_ms_time(current_pos_ms)}")

    def _set_current_pos_as_end(self):
        selected_row = self.track_in_program_manager.get_selected_row()
        if selected_row == -1 or not self.track_in_program_manager.current_program_data: return

        program_tracks = self.track_in_program_manager._get_program_tracks_list()
        if 0 <= selected_row < len(program_tracks):
            current_pos_ms = self.media_player.position()
            track_entry = program_tracks[selected_row]
            start_ms = track_entry.get("user_start_time_ms", 0)

            if current_pos_ms <= 0:  # User wants to clear custom end time
                user_choice = QMessageBox.question(self, "Confirm End Time",
                                                   "Clear custom end time? (Track will play to its detected end)",
                                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                                   QMessageBox.StandardButton.Yes)
                if user_choice == QMessageBox.StandardButton.Yes:
                    track_entry["user_end_time_ms"] = None  # None signifies play to actual track end
                    end_spin = self.track_in_program_manager.tracks_table_widget.cellWidget(selected_row,
                                                                                            AudioTrackInProgramManager.COL_END_TIME)
                    if end_spin: end_spin.setValue(0)  # Spinbox shows "Track End" for 0
                    self.track_in_program_manager.program_tracks_updated.emit()
                    QMessageBox.information(self, "Time Set",
                                            "Custom end time cleared. Track will play to its actual end.")
                return

            if current_pos_ms < start_ms:
                QMessageBox.warning(self, "Invalid End Time", "End time cannot be before start time.")
                return

            detected_duration = self.current_track_duration_ms
            if detected_duration > 0 and current_pos_ms > detected_duration:  # End cannot be after full track end
                QMessageBox.warning(self, "Invalid Time",
                                    f"End time ({self._format_ms_time(current_pos_ms)}) cannot be after the track's detected end ({self._format_ms_time(detected_duration)}).")
                return

            track_entry["user_end_time_ms"] = current_pos_ms

            end_spin = self.track_in_program_manager.tracks_table_widget.cellWidget(selected_row,
                                                                                    AudioTrackInProgramManager.COL_END_TIME)
            if end_spin: end_spin.setValue(current_pos_ms)

            self.track_in_program_manager.program_tracks_updated.emit()
            QMessageBox.information(self, "Time Set", f"End time set to {self._format_ms_time(current_pos_ms)}")

    def closeEvent(self, event):
        logger.debug("AudioProgramEditorWindow closeEvent triggered.")
        self.media_player.stop()
        if self.prompt_save_changes():
            event.accept()
            logger.info("AudioProgramEditorWindow closing.")
        else:
            event.ignore()
            logger.info("AudioProgramEditorWindow close cancelled by user.")

    def prompt_save_changes(self):
        if not self.isWindowModified(): return True
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "There are unsaved changes in the audio programs.\nSave them now?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)
        if reply == QMessageBox.StandardButton.Save:
            self.save_all_changes()
            return not self.isWindowModified()
        return reply != QMessageBox.StandardButton.Cancel

    # (Make sure all other methods like add_program, rename_program, save_all_changes etc. are present)