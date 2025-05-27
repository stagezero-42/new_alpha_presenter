# myapp/gui/widget_helpers.py
import logging  # Import logging
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QIcon
from ..utils.paths import get_icon_file_path

# Get the logger for this specific module
logger = logging.getLogger(__name__)

def create_button(text, icon_name=None, tooltip=None, on_click=None):
    """
    Creates and configures a QPushButton instance.

    Args:
        text (str): The text to display on the button.
        icon_name (str, optional): The filename of the icon in the assets/icons
                                   directory. Defaults to None.
        tooltip (str, optional): The tooltip text for the button.
                                 Defaults to None.
        on_click (callable, optional): The function or method to connect to
                                       the button's clicked signal.
                                       Defaults to None.

    Returns:
        QPushButton: The configured QPushButton instance.
    """
    logger.debug(f"Creating button with text: '{text}', icon: '{icon_name}'")
    button = QPushButton(text)

    if icon_name:
        try:
            icon_path = get_icon_file_path(icon_name) #
            if icon_path: # Ensure path is not None or empty
                button.setIcon(QIcon(icon_path))
                logger.debug(f"Set icon '{icon_name}' from path '{icon_path}' for button '{text}'.")
            else:
                logger.warning(f"Icon path for '{icon_name}' not found for button '{text}'.")
        except Exception as e:
            logger.error(f"Could not load icon '{icon_name}' for button '{text}': {e}", exc_info=True)

    if tooltip:
        button.setToolTip(tooltip)
        logger.debug(f"Set tooltip '{tooltip}' for button '{text}'.")

    if on_click and callable(on_click):
        button.clicked.connect(on_click)
        logger.debug(f"Connected click event for button '{text}' to {on_click.__name__ if hasattr(on_click, '__name__') else str(on_click)}.")
    elif on_click:
        logger.warning(f"Provided on_click for button '{text}' is not callable: {on_click}")


    return button