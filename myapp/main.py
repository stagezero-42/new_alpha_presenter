# main.py
import sys
from PySide6.QtWidgets import QApplication
from gui.display_window import DisplayWindow
from gui.control_window import ControlWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    screens = app.screens()

    # Set DisplayWindow on the second screen if available, otherwise use primary
    display_screen = screens[1] if len(screens) > 1 else screens[0]
    display_window = DisplayWindow()
    display_window.setGeometry(display_screen.geometry())
    display_window.showFullScreen()

    # Set ControlWindow on the primary screen
    control_window = ControlWindow(display_window)
    control_window.show()

    sys.exit(app.exec())
