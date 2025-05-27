# tests/test_media/test_media_renderer.py
import pytest
import os
import sys
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt
# --- NEW IMPORT ---
from unittest.mock import patch
# --- END NEW IMPORT ---

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.media.media_renderer import MediaRenderer

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

@pytest.fixture
def media_renderer(qapp):
    window = MediaRenderer()
    window.resize(800, 600)
    return window

@pytest.fixture
def test_media_path(tmp_path):
    # This now just needs to exist for dummy file creation
    media_path = tmp_path / "media_for_testing"
    media_path.mkdir()
    return str(media_path)

def create_dummy_png(path, width=10, height=10):
    if not os.path.exists(path):
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.save(path, "PNG")

def test_media_renderer_creation(media_renderer):
    assert media_renderer is not None
    assert media_renderer.scene is not None
    assert media_renderer.view is not None
    assert media_renderer.windowTitle() == "Display Window"

# --- MODIFIED: Patch get_media_file_path and update display_images call ---
@patch('myapp.media.media_renderer.get_media_file_path')
def test_display_single_valid_image(mock_get_path, media_renderer, test_media_path, qapp):
    dummy_image_name = "dummy_image1.png"
    dummy_image_full_path = os.path.join(test_media_path, dummy_image_name)
    create_dummy_png(dummy_image_full_path)

    # Mock the path helper to return our temp file
    mock_get_path.return_value = dummy_image_full_path

    image_filenames = [dummy_image_name]
    media_renderer.display_images(image_filenames) # Call without base path
    qapp.processEvents()

    mock_get_path.assert_called_once_with(dummy_image_name) # Check it was called
    items = media_renderer.scene.items()
    assert len(items) == 1
    assert isinstance(items[0], QGraphicsPixmapItem)
# --- END MODIFIED ---

# --- MODIFIED: Patch get_media_file_path and update display_images call ---
@patch('myapp.media.media_renderer.get_media_file_path')
def test_clear_display(mock_get_path, media_renderer, test_media_path, qapp):
    dummy_image_name = "dummy_image1.png"
    dummy_image_full_path = os.path.join(test_media_path, dummy_image_name)
    create_dummy_png(dummy_image_full_path)
    mock_get_path.return_value = dummy_image_full_path

    media_renderer.display_images([dummy_image_name]) # Call without base path
    qapp.processEvents()
    assert len(media_renderer.scene.items()) == 1

    media_renderer.clear_display()
    qapp.processEvents()
    assert len(media_renderer.scene.items()) == 0
# --- END MODIFIED ---