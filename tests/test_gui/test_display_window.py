# tests/test_gui/test_display_window.py
import pytest
import os
import sys
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QTimer  # For running assertions after event loop processes

# Ensure the myapp directory is in the Python path
# This allows importing modules from myapp (e.g., myapp.gui.display_window)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.gui.display_window import DisplayWindow


# --- Test Fixtures ---
@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication instance for all tests that need it."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def display_window(qapp):
    """Fixture to create and show a DisplayWindow instance."""
    window = DisplayWindow()
    # window.show() # Showing might not be necessary for all logic tests but can be for geometry
    # For tests, ensure a fixed size to make assertions on scaling/positioning predictable
    window.resize(800, 600)
    return window


@pytest.fixture
def test_media_path():
    """Returns the absolute path to the test media files directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "media_files_for_testing"))


# --- Helper Functions ---
def create_dummy_png(path, width=10, height=10):
    """Creates a minimal dummy PNG file at the given path if it doesn't exist."""
    if not os.path.exists(path):
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)  # or some color
        # For simplicity, this test helper doesn't draw complex things, just creates a valid pixmap
        # In a real scenario, you'd save a pre-made dummy PNG.
        # For PySide6, saving a QPixmap directly to a file requires QImageWriter or similar.
        # It's easier to assume these dummy files are manually created for the test suite.
        # This function will primarily serve to ensure the directory exists.
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Simulate file creation for test logic; actual file must exist for QPixmap to load it.
        # If you can't ensure files exist, mock QPixmap.
        # For this example, we'll assume dummy_image1.png and dummy_image2.png are present.
        if "dummy_image" in os.path.basename(path):  # Only "create" known dummy images
            try:
                # Attempt to save a simple pixmap. This is a basic way.
                # A real test suite would have these files pre-existing.
                img = QPixmap(1, 1)
                img.fill(Qt.GlobalColor.black)
                img.save(path, "PNG")
            except Exception as e:
                print(f"Could not create dummy png {path}: {e}. Ensure it exists manually.")


def create_dummy_txt(path, content="dummy text"):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)


# --- Test Cases ---
def test_display_window_creation(display_window):
    """Test if the DisplayWindow is created successfully."""
    assert display_window is not None
    assert display_window.scene is not None
    assert display_window.view is not None
    assert display_window.windowTitle() == "Display Window"


def test_display_single_valid_image(display_window, test_media_path, qapp, capsys):
    """Test displaying a single valid image."""
    dummy_image_name = "dummy_image1.png"
    create_dummy_png(os.path.join(test_media_path, dummy_image_name))  # Ensure file exists

    image_paths = [dummy_image_name]
    display_window.display_images(image_paths, test_media_path)

    # Allow Qt event loop to process
    qapp.processEvents()

    items = display_window.scene.items()
    assert len(items) == 1
    assert isinstance(items[0], QGraphicsPixmapItem)
    assert not items[0].pixmap().isNull()
    assert items[0].zValue() == 0

    captured = capsys.readouterr()
    assert f"Image not found" not in captured.out
    assert f"Failed to load image" not in captured.out


def test_display_multiple_images_layering(display_window, test_media_path, qapp, capsys):
    """Test displaying multiple images and their layering (zValue)."""
    dummy_image1_name = "dummy_image1.png"
    dummy_image2_name = "dummy_image2.png"
    create_dummy_png(os.path.join(test_media_path, dummy_image1_name))
    create_dummy_png(os.path.join(test_media_path, dummy_image2_name))

    image_paths = [dummy_image1_name, dummy_image2_name]
    display_window.display_images(image_paths, test_media_path)
    qapp.processEvents()

    items = display_window.scene.items()
    # Items are returned in descending Z-order by default from scene.items()
    # So items[0] should be image2 (z=1), items[1] should be image1 (z=0)
    # Or sort them by zValue for robust checking.
    sorted_items = sorted(items, key=lambda item: item.zValue())

    assert len(sorted_items) == 2
    assert isinstance(sorted_items[0], QGraphicsPixmapItem)
    assert not sorted_items[0].pixmap().isNull()
    assert sorted_items[0].zValue() == 0  # First image in list

    assert isinstance(sorted_items[1], QGraphicsPixmapItem)
    assert not sorted_items[1].pixmap().isNull()
    assert sorted_items[1].zValue() == 1  # Second image in list

    captured = capsys.readouterr()
    assert f"Image not found" not in captured.out
    assert f"Failed to load image" not in captured.out


def test_display_missing_image(display_window, test_media_path, qapp, capsys):
    """Test behavior when an image file is missing."""
    image_paths = ["non_existent_image.png"]
    display_window.display_images(image_paths, test_media_path)
    qapp.processEvents()

    items = display_window.scene.items()
    assert len(items) == 0  # No item should be added

    captured = capsys.readouterr()
    assert f"Image not found: {os.path.join(test_media_path, 'non_existent_image.png')}" in captured.out


def test_display_invalid_image_file(display_window, test_media_path, qapp, capsys):
    """Test behavior with a file that is not a valid image."""
    invalid_image_name = "non_image_file.txt"
    create_dummy_txt(os.path.join(test_media_path, invalid_image_name))

    image_paths = [invalid_image_name]
    display_window.display_images(image_paths, test_media_path)
    qapp.processEvents()

    items = display_window.scene.items()
    assert len(items) == 0  # No item should be added if QPixmap isNull

    captured = capsys.readouterr()
    expected_msg_part = f"Failed to load image (or image is invalid): {os.path.join(test_media_path, invalid_image_name)}"
    assert expected_msg_part in captured.out


def test_clear_display(display_window, test_media_path, qapp):
    """Test clearing the display."""
    dummy_image_name = "dummy_image1.png"
    create_dummy_png(os.path.join(test_media_path, dummy_image_name))

    display_window.display_images([dummy_image_name], test_media_path)
    qapp.processEvents()
    assert len(display_window.scene.items()) == 1

    display_window.clear_display()
    qapp.processEvents()
    assert len(display_window.scene.items()) == 0


def test_display_no_images(display_window, test_media_path, qapp, capsys):
    """Test displaying an empty list of images."""
    display_window.display_images([], test_media_path)
    qapp.processEvents()

    items = display_window.scene.items()
    assert len(items) == 0

    captured = capsys.readouterr()
    assert "No images to display for the current slide." in captured.out

# Note: Testing resizeEvent and showEvent behavior accurately often requires more complex
# GUI testing setups (like pytest-qt) to ensure the window is fully processed by the event loop
# and geometry is correctly updated and accessible.
# For now, their basic existence can be confirmed if needed, but their functional impact
# on re-rendering is harder to unit test simply.

