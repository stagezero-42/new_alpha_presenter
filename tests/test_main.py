# tests/test_main.py
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from myapp.main import setup_windows
from PySide6.QtCore import QRect

@pytest.fixture
def mock_qapplication_instance(monkeypatch):
    mock_app = MagicMock()
    mock_app._simulated_screens_list = []
    mock_app.screens = MagicMock(return_value=mock_app._simulated_screens_list)
    return mock_app

def create_mock_screen(name="Screen", x=0, y=0, width=1920, height=1080):
    """Creates a MagicMock object simulating a QScreen."""
    screen = MagicMock()
    # --- THIS IS THE FIX ---
    # Make 'name' a callable mock that returns the provided 'name' string
    screen.name.return_value = name
    # --- END FIX ---
    screen.geometry = MagicMock(return_value=QRect(x, y, width, height))
    return screen

@patch('myapp.main.MediaRenderer', autospec=True)
@patch('myapp.main.ControlWindow', autospec=True)
def test_setup_windows_single_screen(MockControlWindow, MockMediaRenderer, mock_qapplication_instance):
    primary_screen_mock = create_mock_screen(name="Primary", x=0, y=0, width=1920, height=1080)
    mock_qapplication_instance._simulated_screens_list = [primary_screen_mock]
    mock_qapplication_instance.screens.return_value = mock_qapplication_instance._simulated_screens_list

    display_win_mock_instance = MockMediaRenderer.return_value
    control_win_mock_instance = MockControlWindow.return_value

    returned_display_win, returned_control_win = setup_windows(mock_qapplication_instance)

    MockMediaRenderer.assert_called_once()
    display_win_mock_instance.setGeometry.assert_called_once_with(QRect(0, 0, 1920, 1080))
    # --- MODIFIED: Assert NOT called ---
    display_win_mock_instance.showFullScreen.assert_not_called()
    # --- END MODIFIED ---
    assert returned_display_win is display_win_mock_instance

    MockControlWindow.assert_called_once_with(display_win_mock_instance)
    control_win_mock_instance.show.assert_called_once()
    assert returned_control_win is control_win_mock_instance

@patch('myapp.main.MediaRenderer', autospec=True)
@patch('myapp.main.ControlWindow', autospec=True)
def test_setup_windows_dual_screen(MockControlWindow, MockMediaRenderer, mock_qapplication_instance):
    primary_screen_mock = create_mock_screen(name="Primary", x=0, y=0, width=1920, height=1080)
    secondary_screen_mock = create_mock_screen(name="Secondary", x=1920, y=0, width=1280, height=720)
    mock_qapplication_instance._simulated_screens_list = [primary_screen_mock, secondary_screen_mock]
    mock_qapplication_instance.screens.return_value = mock_qapplication_instance._simulated_screens_list

    display_win_mock_instance = MockMediaRenderer.return_value
    control_win_mock_instance = MockControlWindow.return_value

    returned_display_win, returned_control_win = setup_windows(mock_qapplication_instance)

    MockMediaRenderer.assert_called_once()
    display_win_mock_instance.setGeometry.assert_called_once_with(QRect(1920, 0, 1280, 720))
    # --- MODIFIED: Assert NOT called ---
    display_win_mock_instance.showFullScreen.assert_not_called()
    # --- END MODIFIED ---
    assert returned_display_win is display_win_mock_instance

    MockControlWindow.assert_called_once_with(display_win_mock_instance)
    control_win_mock_instance.show.assert_called_once()
    assert returned_control_win is control_win_mock_instance