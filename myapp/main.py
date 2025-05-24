# myapp/main.py
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QRect

from .media.media_renderer import MediaRenderer
from .gui.control_window import ControlWindow

def setup_windows(app):
    """
    Sets up and returns the display and control windows based on screen availability.
    The display window is created but NOT shown by default.
    """
    screens = app.screens()
    display_window_instance = MediaRenderer()
    control_window_instance = ControlWindow(display_window_instance)

    display_screen_geometry = None

    if screens:
        display_target_screen = screens[1] if len(screens) > 1 else screens[0]
        display_screen_geometry = display_target_screen.geometry()
    else:
        # Fallback if no screens detected (though we check earlier now)
        display_screen_geometry = QRect(0, 0, 800, 600)

    if display_screen_geometry:
        display_window_instance.setGeometry(display_screen_geometry)

    # --- CHANGE: DO NOT SHOW THE DISPLAY WINDOW ON STARTUP ---
    # display_window_instance.showFullScreen()
    # --- END CHANGE ---

    control_window_instance.show()

    return display_window_instance, control_window_instance


def run_application():
    """
    Initializes and runs the QApplication.
    """
    app = QApplication(sys.argv)

    if not app.screens():
        QMessageBox.critical(None, "Startup Error", "No screens detected by QApplication. Exiting.")
        return 1  # Return an error code

    _display_win, _control_win = setup_windows(app)

    return app.exec()


if __name__ == "__main__":
    exit_code = run_application()
    sys.exit(exit_code)