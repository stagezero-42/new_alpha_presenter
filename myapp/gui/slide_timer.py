# myapp/gui/slide_timer.py
import logging # Import logging
from PySide6.QtCore import QObject, QTimer, Signal

# Get the logger for this specific module
logger = logging.getLogger(__name__)

class SlideTimer(QObject):
    """
    Manages the QTimer for automatic slide advancement and looping.
    """
    timeout_action_required = Signal()

    def __init__(self, parent=None):
        """
        Initializes the SlideTimer.

        Args:
            parent (QObject, optional): Parent object. Defaults to None.
        """
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._handle_timeout) # Connect to internal handler
        logger.debug("SlideTimer initialized.")

    def _handle_timeout(self):
        """Internal handler for QTimer's timeout signal."""
        logger.debug("SlideTimer internal timeout triggered. Emitting timeout_action_required signal.")
        self.timeout_action_required.emit()

    def start(self, duration_seconds):
        """
        Starts the timer for the given duration.

        Args:
            duration_seconds (int): The duration in seconds.
        """
        if duration_seconds > 0:
            logger.info(f"SlideTimer: Starting for {duration_seconds} seconds.")
            self._timer.start(duration_seconds * 1000)
        else:
            logger.debug("SlideTimer: Duration is 0 seconds, timer not started.")

    def stop(self):
        """Stops the timer if it is active."""
        if self._timer.isActive():
            logger.info("SlideTimer: Stopping.")
            self._timer.stop()
        else:
            logger.debug("SlideTimer: Stop called, but timer was not active.")

    def is_active(self):
        """
        Checks if the timer is currently active.

        Returns:
            bool: True if the timer is active, False otherwise.
        """
        active = self._timer.isActive()
        logger.debug(f"SlideTimer: is_active check, returning {active}.")
        return active