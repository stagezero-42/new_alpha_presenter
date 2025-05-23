# tests/test_main.py
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure myapp is in path for imports like myapp.main
# This assumes tests are run from the project root or this path adjustment is effective.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# This import will work if myapp/main.py has the setup_windows function
# and myapp/__init__.py exists.
from myapp.main import setup_windows
from PySide6.QtCore import QRect  # For creating mock geometry and comparing


@pytest.fixture
def mock_qapplication_instance(monkeypatch):
    """
    Mocks a QApplication instance and its screens() method.
    Allows tests to control the list of screens returned.
    """
    mock_app = MagicMock()
    # This list will be populated by tests to simulate different screen setups
    mock_app._simulated_screens_list = []
    mock_app.screens = MagicMock(return_value=mock_app._simulated_screens_list)

    # If QApplication class itself needs to be mocked for instantiation within main script part:
    # mock_qapplication_class = MagicMock(return_value=mock_app)
    # monkeypatch.setattr("myapp.main.QApplication", mock_qapplication_class)
    return mock_app


def create_mock_screen(name="Screen", x=0, y=0, width=1920, height=1080):
    """Helper to create a mock QScreen object."""
    screen = MagicMock()
    screen.name = name
    screen.geometry = MagicMock(return_value=QRect(x, y, width, height))
    return screen


# We need to patch where DisplayWindow and ControlWindow are *looked up* by myapp.main
# If myapp.main.py has "from .gui.display_window import DisplayWindow",
# then the name "DisplayWindow" exists in the myapp.main module's namespace.
@patch('myapp.main.DisplayWindow', autospec=True)
@patch('myapp.main.ControlWindow', autospec=True)
def test_setup_windows_single_screen(MockControlWindow, MockDisplayWindow, mock_qapplication_instance):
    """Test window setup logic with a single screen detected."""
    # Configure the mock QApplication to return one screen
    primary_screen_mock = create_mock_screen(name="Primary", x=0, y=0, width=1920, height=1080)
    mock_qapplication_instance._simulated_screens_list = [primary_screen_mock]
    mock_qapplication_instance.screens.return_value = mock_qapplication_instance._simulated_screens_list

    # Call the setup function from main.py
    # setup_windows is expected to instantiate DisplayWindow and ControlWindow
    # The patched versions (MockDisplayWindow, MockControlWindow) will be used.
    # Their return values are MagicMock instances by default.
    display_win_mock_instance = MockDisplayWindow.return_value
    control_win_mock_instance = MockControlWindow.return_value

    returned_display_win, returned_control_win = setup_windows(mock_qapplication_instance)

    # Assert DisplayWindow was instantiated and configured for the primary screen
    MockDisplayWindow.assert_called_once()  # Check it was instantiated
    # Check methods called on the instance returned by the mocked constructor
    display_win_mock_instance.setGeometry.assert_called_once_with(QRect(0, 0, 1920, 1080))
    display_win_mock_instance.showFullScreen.assert_called_once()
    assert returned_display_win is display_win_mock_instance

    # Assert ControlWindow was instantiated and shown
    MockControlWindow.assert_called_once_with(display_win_mock_instance)  # Check it received the display window mock
    control_win_mock_instance.show.assert_called_once()
    assert returned_control_win is control_win_mock_instance


@patch('myapp.main.DisplayWindow', autospec=True)
@patch('myapp.main.ControlWindow', autospec=True)
def test_setup_windows_dual_screen(MockControlWindow, MockDisplayWindow, mock_qapplication_instance):
    """Test window setup logic with two screens detected."""
    primary_screen_mock = create_mock_screen(name="Primary", x=0, y=0, width=1920, height=1080)
    secondary_screen_mock = create_mock_screen(name="Secondary", x=1920, y=0, width=1280, height=720)
    mock_qapplication_instance._simulated_screens_list = [primary_screen_mock, secondary_screen_mock]
    mock_qapplication_instance.screens.return_value = mock_qapplication_instance._simulated_screens_list

    display_win_mock_instance = MockDisplayWindow.return_value
    control_win_mock_instance = MockControlWindow.return_value

    returned_display_win, returned_control_win = setup_windows(mock_qapplication_instance)

    # Assert DisplayWindow was configured for the secondary screen
    MockDisplayWindow.assert_called_once()
    display_win_mock_instance.setGeometry.assert_called_once_with(
        QRect(1920, 0, 1280, 720))  # Secondary screen's geometry
    display_win_mock_instance.showFullScreen.assert_called_once()
    assert returned_display_win is display_win_mock_instance

    # Assert ControlWindow was instantiated and shown
    MockControlWindow.assert_called_once_with(display_win_mock_instance)
    control_win_mock_instance.show.assert_called_once()
    assert returned_control_win is control_win_mock_instance


@patch('myapp.main.DisplayWindow', autospec=True)
@patch('myapp.main.ControlWindow', autospec=True)
@patch('myapp.main.print')  # Mock the print function used in main for warnings
def test_setup_windows_no_screens_detected(mock_print, MockControlWindow, MockDisplayWindow,
                                           mock_qapplication_instance):
    """
    Test window setup logic when no screens are detected by QApplication.
    This tests the robustness of the setup_windows function itself.
    """
    mock_qapplication_instance._simulated_screens_list = []  # No screens
    mock_qapplication_instance.screens.return_value = mock_qapplication_instance._simulated_screens_list

    display_win_mock_instance = MockDisplayWindow.return_value
    control_win_mock_instance = MockControlWindow.return_value

    returned_display_win, returned_control_win = setup_windows(mock_qapplication_instance)

    # Check if the warning print was called from setup_windows
    mock_print.assert_any_call(
        "Warning: setup_windows called with no screens detected by QApplication! Using defaults.")

    # Assert DisplayWindow was instantiated.
    # Its setGeometry should be called with the default QRect defined in setup_windows.
    MockDisplayWindow.assert_called_once()
    display_win_mock_instance.setGeometry.assert_called_once_with(QRect(0, 0, 800, 600))  # Default geometry
    display_win_mock_instance.showFullScreen.assert_called_once()
    assert returned_display_win is display_win_mock_instance

    # Assert ControlWindow was instantiated and shown
    MockControlWindow.assert_called_once_with(display_win_mock_instance)
    control_win_mock_instance.show.assert_called_once()
    assert returned_control_win is control_win_mock_instance

