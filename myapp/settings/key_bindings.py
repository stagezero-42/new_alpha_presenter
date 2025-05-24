# myapp/settings/key_bindings.py
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt

def setup_keybindings(control_window):
    from PySide6.QtGui import QShortcut # Import QShortcut inside the function

    QShortcut(QKeySequence(Qt.Key.Key_Right), control_window, control_window.next_slide)
    QShortcut(QKeySequence(Qt.Key.Key_Left), control_window, control_window.prev_slide)
    QShortcut(QKeySequence(Qt.Key.Key_Space), control_window, control_window.start_or_go_slide)
    QShortcut(QKeySequence(Qt.Key.Key_Escape), control_window, control_window.clear_display_screen)
    QShortcut(QKeySequence("Ctrl+Q"), control_window, control_window.close_application)
    QShortcut(QKeySequence("Ctrl+L"), control_window, control_window.load_playlist_dialog)
    QShortcut(QKeySequence("Ctrl+E"), control_window, control_window.open_playlist_editor)