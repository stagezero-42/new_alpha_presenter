# myapp/gui/audio_program_list_panel.py
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QLabel, QMessageBox, QInputDialog
)
from PySide6.QtCore import Signal, Qt

from ..audio.audio_program_manager import AudioProgramManager
from ..utils.security import is_safe_filename_component
from .widget_helpers import create_button

logger = logging.getLogger(__name__)


class AudioProgramListPanel(QWidget):
    program_selected = Signal(str)
    program_list_updated = Signal()

    def __init__(self, program_manager: AudioProgramManager, parent=None):
        super().__init__(parent)
        self.program_manager = program_manager
        self._current_selected_program_name_in_panel = None  # Internal state for this panel
        self._block_list_signals = False
        self._setup_ui()
        self.update_button_states()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Audio Programs:"))
        self.program_list_widget = QListWidget()
        self.program_list_widget.currentItemChanged.connect(self._handle_selection_changed_from_widget)
        layout.addWidget(self.program_list_widget)
        buttons_layout = QHBoxLayout()
        self.add_button = create_button("Add", "add.png", "Add New Program", self.add_program)
        self.rename_button = create_button("Rename", "edit.png", "Rename Selected Program", self.rename_program)
        self.delete_button = create_button("Delete", "remove.png", "Delete Selected Program", self.delete_program)
        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.rename_button)
        buttons_layout.addWidget(self.delete_button)
        layout.addLayout(buttons_layout)

    def load_and_list_programs(self, select_program_name=None):
        logger.debug(f"ProgramListPanel: Loading and listing programs. Target selection: '{select_program_name}'")

        self._block_list_signals = True
        # Disconnect temporarily to avoid multiple triggers during clear/repopulate
        try:
            self.program_list_widget.currentItemChanged.disconnect(self._handle_selection_changed_from_widget)
        except RuntimeError:  # Was not connected
            pass

        # Determine what was selected before clearing, to try and restore it if select_program_name is None
        previously_selected_text = None
        if self.program_list_widget.currentItem():
            previously_selected_text = self.program_list_widget.currentItem().text()

        self.program_list_widget.clear()

        program_names = []
        try:
            program_names = sorted(self.program_manager.list_programs())
            self.program_list_widget.addItems(program_names)
        except Exception as e:
            # Log error, but continue to try and set selection if possible
            logger.error(f"Failed to list audio programs: {e}")
            # QMessageBox.critical(self, "Load Error", f"Failed to list audio programs: {e}") # Avoid UI in tests

        final_selection_name = select_program_name  # Prioritize explicit request
        if final_selection_name is None:
            final_selection_name = previously_selected_text  # Fallback to previous selection

        newly_selected_item_for_signal = None
        if final_selection_name and final_selection_name in program_names:
            for i in range(self.program_list_widget.count()):
                if self.program_list_widget.item(i).text() == final_selection_name:
                    self.program_list_widget.setCurrentRow(i)  # This will NOT emit currentItemChanged yet
                    newly_selected_item_for_signal = self.program_list_widget.item(i)
                    break
        elif program_names:  # If no specific or previous selection, or it's no longer valid, select first
            self.program_list_widget.setCurrentRow(0)
            newly_selected_item_for_signal = self.program_list_widget.item(0)
        # If list is empty, newly_selected_item_for_signal remains None

        # Reconnect and then manually trigger the handler for the final state
        self.program_list_widget.currentItemChanged.connect(self._handle_selection_changed_from_widget)
        self._block_list_signals = False  # Allow handler to work

        # Manually call handler with the item that should be selected (or None if list empty/no selection)
        self._handle_selection_changed_from_widget(newly_selected_item_for_signal,
                                                   None)  # previous_item can be None for this manual call

        self.update_button_states()  # Update buttons based on the final selection state

    def _handle_selection_changed_from_widget(self, current_item, previous_item):
        # This method is now primarily called by currentItemChanged signal,
        # OR manually by load_and_list_programs after everything is set up.
        if self._block_list_signals: return

        new_selection_name = current_item.text() if current_item else None

        # Only update and emit if the panel's internal idea of selection actually changes
        if new_selection_name != self._current_selected_program_name_in_panel:
            self._current_selected_program_name_in_panel = new_selection_name
            logger.info(f"ProgramListPanel: Selection changed to: {self._current_selected_program_name_in_panel}")
            self.program_selected.emit(self._current_selected_program_name_in_panel)

        self.update_button_states()  # Always update buttons based on current QListWidget state

    def add_program(self):
        program_name, ok = QInputDialog.getText(self, "New Audio Program", "Enter name for new program:")
        if ok and program_name:
            safe_name = program_name.strip().replace(" ", "_")
            if not safe_name or not is_safe_filename_component(f"{safe_name}.json"):
                QMessageBox.warning(self, "Invalid Name", "Name is empty, contains invalid characters or is reserved.");
                return
            if safe_name in self.program_manager.list_programs():
                QMessageBox.warning(self, "Name Exists", "A program with this name already exists.");
                return

            new_program_data = {"program_name": safe_name, "tracks": [], "loop_indefinitely": False, "loop_count": 0}
            if self.program_manager.save_program(safe_name, new_program_data):
                logger.info(f"ProgramListPanel: Program '{safe_name}' added.")
                self.load_and_list_programs(select_program_name=safe_name)  # This will select and emit
                self.program_list_updated.emit()
            else:
                QMessageBox.critical(self, "Save Error", "Could not save the new audio program.")

    def rename_program(self):
        if not self._current_selected_program_name_in_panel: return
        old_name = self._current_selected_program_name_in_panel
        new_name_input, ok = QInputDialog.getText(self, "Rename Program", f"New name for '{old_name}':", text=old_name)
        if not (ok and new_name_input and new_name_input.strip()): return

        safe_new_name = new_name_input.strip().replace(" ", "_")
        if safe_new_name == old_name: return
        if not is_safe_filename_component(f"{safe_new_name}.json"):
            QMessageBox.warning(self, "Invalid Name", "New name contains invalid characters or is reserved.");
            return

        existing_names_lower = [name.lower() for name in self.program_manager.list_programs() if
                                name.lower() != old_name.lower()]
        if safe_new_name.lower() in existing_names_lower:
            QMessageBox.warning(self, "Name Exists", "A program with the new name already exists.");
            return
        try:
            program_data_to_rename = self.program_manager.load_program(old_name)
            if not program_data_to_rename:
                QMessageBox.critical(self, "Rename Error", f"Could not load '{old_name}' to rename.");
                return
            program_data_to_rename["program_name"] = safe_new_name
            if self.program_manager.save_program(safe_new_name, program_data_to_rename):
                if old_name.lower() != safe_new_name.lower():
                    self.program_manager.delete_program(old_name)
                logger.info(f"ProgramListPanel: Renamed '{old_name}' to '{safe_new_name}'.")
                self.load_and_list_programs(select_program_name=safe_new_name)
                self.program_list_updated.emit()
            else:
                QMessageBox.critical(self, "Save Error", "Could not save renamed program.")
        except Exception as e:
            QMessageBox.critical(self, "Rename Error", f"Failed to rename: {e}")

    def delete_program(self):
        if not self._current_selected_program_name_in_panel: return
        program_to_delete = self._current_selected_program_name_in_panel
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete '{program_to_delete}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.program_manager.delete_program(program_to_delete):
                logger.info(f"ProgramListPanel: Deleted '{program_to_delete}'.")
                self.load_and_list_programs()  # Refresh, will select first or none
                self.program_list_updated.emit()
            else:
                QMessageBox.critical(self, "Delete Error", "Could not delete program file.")

    def get_selected_program_name(self) -> str | None:
        return self._current_selected_program_name_in_panel  # Use internal state

    def select_program(self, program_name: str | None): # Allow None to deselect
        logger.debug(f"ProgramListPanel: Programmatically selecting '{program_name}'")
        # This method is now simpler: just call load_and_list_programs with the target.
        # load_and_list_programs will handle the QListWidget selection and signal emission.
        self.load_and_list_programs(select_program_name=program_name)

    def update_button_states(self):
        has_selection = self._current_selected_program_name_in_panel is not None
        self.rename_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)