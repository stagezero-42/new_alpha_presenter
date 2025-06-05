# myapp/main.py
import sys
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QRect

from .media.media_renderer import MediaRenderer
from .gui.control_window import ControlWindow
from .utils.paths import ensure_assets_folders_exist
from .utils.logger_config import setup_logging
# SettingsManager is used by setup_logging internally now.

def setup_windows(app):
    logger = logging.getLogger(__name__)
    logger.info("Setting up windows...")
    screens = app.screens()
    display_window_instance = MediaRenderer()
    control_window_instance = ControlWindow(display_window_instance)
    display_screen_geometry = None
    if screens:
        display_target_screen = screens[1] if len(screens) > 1 else screens[0]
        logger.info(f"Detected {len(screens)} screen(s). Display target: {display_target_screen.name()}")
        display_screen_geometry = display_target_screen.geometry()
    else:
        logger.warning("No screens detected by QApplication! Using default geometry.")
        display_screen_geometry = QRect(0, 0, 800, 600)
    if display_screen_geometry:
        display_window_instance.setGeometry(display_screen_geometry)
    control_window_instance.show()
    logger.info("Windows setup complete.")
    return display_window_instance, control_window_instance

def run_application():
    ensure_assets_folders_exist()
    try:
        # Corrected: setup_logging will now internally use SettingsManager
        setup_logging()
    except Exception as e:
        # Fallback if settings fail - use print as logging might not work
        print(f"FATAL: Could not set up logging: {e}")
        # Attempt basic logging if advanced setup fails
        logging.basicConfig(level=logging.INFO) # Or logging.DEBUG for more info
        logging.error(f"Fell back to basic logging config due to error: {e}", exc_info=True)


    logger = logging.getLogger(__name__) # Get logger instance after setup
    logger.info("------------------------------------")
    logger.info("New Alpha Presenter Application Starting...")

    app = QApplication(sys.argv)
    if not app.screens():
        logger.critical("No screens detected by QApplication. Exiting.")
        QMessageBox.critical(None, "Startup Error", "No screens detected by QApplication. Exiting.")
        return 1
    _display_win, _control_win = setup_windows(app)
    exit_code = app.exec()
    logger.info(f"Application exiting with code {exit_code}.")
    return exit_code

if __name__ == "__main__":
    exit_code = run_application()
    sys.exit(exit_code)