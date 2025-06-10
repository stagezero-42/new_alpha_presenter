# myapp/gui/settings_window.py
import os
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QHBoxLayout,
    QGroupBox, QMessageBox, QDialogButtonBox
)
from PySide6.QtGui import QIcon
from ..settings.settings_manager import SettingsManager
from ..utils.paths import get_icon_file_path
from .help_window import HelpWindow
from .widget_helpers import create_button

logger = logging.getLogger(__name__)

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Initializing SettingsWindow...")
        self.setWindowTitle("Application Settings")
        self.settings_manager = SettingsManager()
        self.setMinimumWidth(450)
        self.help_window_instance = None

        # Set window icon
        try:
            icon_path = get_icon_file_path("settings.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set SettingsWindow icon: {e}", exc_info=True)

        self.setup_ui()
        self.load_settings()
        logger.debug("SettingsWindow initialized.")

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Keybindings Group ---
        keybindings_group = QGroupBox("Keybindings (Enter comma-separated keys)")
        keybindings_layout = QFormLayout()

        self.key_widgets = {}
        key_actions = ["next", "prev", "go", "clear", "quit", "load", "edit"]
        for action in key_actions:
            self.key_widgets[action] = QLineEdit()
            self.key_widgets[action].setToolTip(f"Default: {', '.join(self.settings_manager._load_defaults()['keybindings'].get(action, []))}")
            keybindings_layout.addRow(f"{action.capitalize()}:", self.key_widgets[action])

        keybindings_group.setLayout(keybindings_layout)
        main_layout.addWidget(keybindings_group)

        # --- Logging Group ---
        logging_group = QGroupBox("Logging")
        logging_layout = QFormLayout()

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        logging_layout.addRow("Log Level:", self.log_level_combo)

        self.log_to_file_check = QCheckBox("Log to File")
        logging_layout.addRow("", self.log_to_file_check)

        self.log_file_path_edit = QLineEdit()
        logging_layout.addRow("Log File Path:", self.log_file_path_edit)

        logging_group.setLayout(logging_layout)
        main_layout.addWidget(logging_group)

        # --- Buttons ---
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Help)
        self.button_box.accepted.connect(self.accept_changes)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_changes)
        self.button_box.helpRequested.connect(self.open_help_window)
        main_layout.addWidget(self.button_box)

    def load_settings(self):
        """Load current settings into the UI widgets."""
        logger.debug("Loading settings into UI.")
        current_settings = self.settings_manager.settings

        # Load Keybindings
        keybindings = current_settings.get("keybindings", {})
        for action, widget in self.key_widgets.items():
            keys = keybindings.get(action, [])
            widget.setText(", ".join(keys))

        # Load Logging
        self.log_level_combo.setCurrentText(current_settings.get("log_level", "INFO"))
        self.log_to_file_check.setChecked(current_settings.get("log_to_file", False))
        self.log_file_path_edit.setText(current_settings.get("log_file_path", "alphapresenter.log"))

    def apply_changes(self):
        """Save the current UI settings without closing."""
        logger.info("Applying settings changes...")
        try:
            # Save Keybindings
            new_keybindings = {}
            for action, widget in self.key_widgets.items():
                keys_str = widget.text().strip()
                # Split by comma, strip whitespace, remove empty strings
                new_keybindings[action] = [key.strip() for key in keys_str.split(',') if key.strip()]
            self.settings_manager.set_setting("keybindings", new_keybindings)

            # Save Logging
            self.settings_manager.set_setting("log_level", self.log_level_combo.currentText())
            self.settings_manager.set_setting("log_to_file", self.log_to_file_check.isChecked())
            self.settings_manager.set_setting("log_file_path", self.log_file_path_edit.text())

            self.settings_manager.save_settings() # Ensure explicit save
            logger.info("Settings applied successfully.")
            QMessageBox.information(self, "Settings Applied",
                                    "Settings have been saved.\n"
                                    "Some changes (like logging and keybindings) "
                                    "may require an application restart to take full effect.")
            return True
        except Exception as e:
            logger.error(f"Error applying settings: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to apply settings: {e}")
            return False

    def open_help_window(self):
        if self.help_window_instance is None or not self.help_window_instance.isVisible():
            self.help_window_instance = HelpWindow(self, anchor="settings_window")
            self.help_window_instance.show()
        else:
            self.help_window_instance.activateWindow()
            self.help_window_instance.raise_()

    def accept_changes(self):
        """Apply changes and close the dialog."""
        if self.apply_changes():
            self.accept()