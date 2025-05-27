# myapp/settings/key_bindings.py
import logging  # Import logging
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)  # Get logger for this module

def setup_keybindings(control_window, settings_manager):
    """Sets up keybindings based on settings."""

    keybindings_config = settings_manager.get_setting("keybindings", {})

    action_map = {
        "next": control_window.next_slide,
        "prev": control_window.prev_slide,
        "go": control_window.handle_show_clear_click,
        "clear": control_window.clear_display_screen,
        "quit": control_window.close_application,
        "load": control_window.load_playlist_dialog,
        "edit": control_window.open_playlist_editor
    }

    logger.info("Setting up keybindings...")
    for action_name, keys_list in keybindings_config.items():
        if action_name in action_map and isinstance(keys_list, list):
            for key_str in keys_list:
                sequence = QKeySequence()

                try:
                    temp_sequence = QKeySequence(key_str)
                    if not temp_sequence.isEmpty():
                        sequence = temp_sequence
                except Exception:
                    pass

                if not sequence.isEmpty():
                    try:
                        shortcut = QShortcut(sequence, control_window)
                        shortcut.activated.connect(action_map[action_name])
                        logger.info(f"  - Mapped '{key_str}' (Seq: {sequence.toString()}) to '{action_name}'")
                    except Exception as e:
                        logger.error(f"  - Error creating shortcut for '{key_str}': {e}", exc_info=True)
                else:
                    logger.warning(f"  - Could not parse key '{key_str}' for action '{action_name}'")
        else:
            logger.warning(f"  - Action '{action_name}' not found in action_map or keys not a list.")