# myapp/gui/widget_helpers.py
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QIcon
from ..utils.paths import get_icon_file_path

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
    button = QPushButton(text)

    if icon_name:
        try:
            icon_path = get_icon_file_path(icon_name)
            button.setIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Warning: Could not load icon '{icon_name}': {e}")

    if tooltip:
        button.setToolTip(tooltip)

    if on_click and callable(on_click):
        button.clicked.connect(on_click)

    return button