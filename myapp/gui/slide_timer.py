# myapp/gui/slide_timer.py
from PySide6.QtCore import QObject, QTimer, Signal

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
        self._timer.timeout.connect(self.timeout_action_required.emit)

    def start(self, duration_seconds):
        """
        Starts the timer for the given duration.

        Args:
            duration_seconds (int): The duration in seconds.
        """
        if duration_seconds > 0:
            print(f"SlideTimer: Starting for {duration_seconds} seconds.")
            self._timer.start(duration_seconds * 1000)
        else:
            print("SlideTimer: Duration is 0, not starting.")

    def stop(self):
        """Stops the timer if it is active."""
        if self._timer.isActive():
            print("SlideTimer: Stopping.")
            self._timer.stop()

    def is_active(self):
        """
        Checks if the timer is currently active.

        Returns:
            bool: True if the timer is active, False otherwise.
        """
        return self._timer.isActive()