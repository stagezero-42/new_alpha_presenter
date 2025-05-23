# myapp/main.py
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QRect

from .gui.display_window import DisplayWindow
from .gui.control_window import ControlWindow


def setup_windows(app):
    """
    Sets up and returns the display and control windows based on screen availability.
    """
    screens = app.screens()
    display_window_instance = DisplayWindow()
    control_window_instance = ControlWindow(display_window_instance)

    display_screen_geometry = None
    # primary_screen_for_control = None # Not explicitly used for placement in current logic

    if screens:
        display_target_screen = screens[1] if len(screens) > 1 else screens[0]
        display_screen_geometry = display_target_screen.geometry()

        # primary_screen_for_control = screens[0] # Available if needed
    else:
        print("Warning: setup_windows called with no screens detected by QApplication! Using defaults.")
        display_screen_geometry = QRect(0, 0, 800, 600)

    if display_screen_geometry:
        display_window_instance.setGeometry(display_screen_geometry)
    display_window_instance.showFullScreen()

    control_window_instance.show()

    return display_window_instance, control_window_instance


def run_application():
    """
    Initializes and runs the QApplication.
    This function contains the logic previously in the if __name__ == "__main__": block.
    """
    app = QApplication(sys.argv)

    if not app.screens():
        print("Critical Error: No screens detected by QApplication. The application cannot start.")
        QMessageBox.critical(None, "Startup Error", "No screens detected by QApplication. Exiting.")
        return 1  # Return an error code

    _display_win, _control_win = setup_windows(app)  # Underscore to indicate they are not used after this

    return app.exec()  # This will eventually lead to sys.exit(app.exec())


if __name__ == "__main__":
    exit_code = run_application()
    sys.exit(exit_code)
