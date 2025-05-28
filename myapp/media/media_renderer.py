# myapp/media/media_renderer.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    # --- NEW IMPORTS ---
    QGraphicsTextItem
    # --- END NEW IMPORTS ---
)
from PySide6.QtGui import (
    QPixmap, QPainter, QBrush, QColor, QIcon,
    # --- NEW IMPORTS ---
    QFont
    # --- END NEW IMPORTS ---
)
from PySide6.QtCore import Qt, QRectF
from ..utils.paths import get_media_file_path, get_icon_file_path

logger = logging.getLogger(__name__)

class MediaRenderer(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.debug("Initializing MediaRenderer...")
        self.setWindowTitle("Display Window")

        try:
            icon_name = "app_icon.png" # Main app icon
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logger.debug(f"Set window icon for MediaRenderer from: {icon_path}")
            else:
                logger.warning(f"MediaRenderer icon '{icon_name}' not found.")
        except Exception as e:
            logger.error(f"Failed to set MediaRenderer window icon: {e}", exc_info=True)

        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)

        self.view.setBackgroundBrush(QBrush(QColor(0, 0, 0)))
        self.view.setStyleSheet("border: 0px")

        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.setCentralWidget(self.view)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.current_layers = []
        # --- NEW ATTRIBUTES ---
        self.text_item = None # To hold the current QGraphicsTextItem
        self.current_text = None # To store the current text content
        # --- END NEW ATTRIBUTES ---
        logger.debug("MediaRenderer initialized.")

    def display_images(self, image_filenames):
        """Display a list of images with layering.
           image_filenames: List of *just filenames*.
           This will clear previous images BUT NOT TEXT.
        """
        logger.debug(f"Displaying images: {image_filenames}")

        # --- MODIFIED: Remove only QGraphicsPixmapItems ---
        # Store text item temporarily
        current_text_item = self.text_item
        if current_text_item and current_text_item in self.scene.items():
             self.scene.removeItem(current_text_item) # Remove to re-add later if needed

        # Clear only images (or everything and re-add text) - Simpler to clear all and re-add
        self.scene.clear() # Clear everything (images and old text pos)
        self.text_item = None # Reset text_item since it was cleared
        # --- END MODIFIED ---

        self.current_layers = image_filenames

        if not image_filenames:
            logger.info("No images to display for the current slide.")
            # --- MODIFIED: If text exists, display it even without images ---
            if self.current_text:
                self.displayText(self.current_text)
            # --- END MODIFIED ---
            return

        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty(): view_rect = self.rect()
        if view_rect.isEmpty():
            logger.warning("View or window rect is empty, cannot scale images.")
            # --- MODIFIED: Still try to show text ---
            if self.current_text:
                 self.displayText(self.current_text)
            # --- END MODIFIED ---
            return

        for i, filename in enumerate(image_filenames):
            full_path = get_media_file_path(filename)

            if not os.path.exists(full_path):
                logger.warning(f"Image not found: {full_path}")
                continue

            pixmap = QPixmap(full_path)
            if pixmap.isNull():
                logger.warning(f"Failed to load image: {full_path}")
                continue

            pixmap_scaled = pixmap.scaled(view_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            item = QGraphicsPixmapItem(pixmap_scaled)
            item.setPos((view_rect.width() - pixmap_scaled.width()) / 2,
                        (view_rect.height() - pixmap_scaled.height()) / 2)
            item.setZValue(i) # Images have lower Z-values
            self.scene.addItem(item)

        self.scene.setSceneRect(QRectF(view_rect))
        logger.debug("Image display complete.")

        # --- MODIFIED: Re-display text if it exists ---
        if self.current_text:
            self.displayText(self.current_text)
        # --- END MODIFIED ---


    # --- NEW METHOD ---
    def displayText(self, text_to_display):
        """
        Displays text as an overlay on the scene.
        Uses hardcoded style and bottom-center position.
        """
        self.clearText() # Clear any existing text first

        self.current_text = text_to_display # Store the text

        if not text_to_display:
            logger.debug("displayText called with empty text, clearing.")
            return

        logger.debug(f"Displaying text: '{text_to_display}'")

        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty(): view_rect = self.rect()
        if view_rect.isEmpty():
            logger.warning("View or window rect is empty, cannot display text.")
            return

        # Create the text item
        self.text_item = QGraphicsTextItem()

        # Hardcoded style (White text, 48pt Bold Arial, semi-transparent black bg)
        font = QFont("Arial", 48, QFont.Weight.Bold)
        text_color = "white"
        bg_color = "rgba(0, 0, 0, 150)" # Black with ~60% opacity
        padding = "15px"
        border_radius = "10px"

        # Use HTML for basic styling (background, padding, color)
        # Note: QGraphicsTextItem HTML support is basic.
        html_content = (
            f"<div style='background-color: {bg_color}; "
            f"color: {text_color}; "
            f"padding: {padding}; "
            f"border-radius: {border_radius};'>"
            f"{text_to_display.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace(' ', '&nbsp;').replace('\\n', '<br/>')}" # Basic escaping
            f"</div>"
        )

        self.text_item.setHtml(html_content)
        self.text_item.setFont(font) # Font needs to be set separately

        # Set Z-value to ensure text is on top
        self.text_item.setZValue(1000)

        # Calculate position (Bottom Center)
        text_rect = self.text_item.boundingRect()
        view_width = view_rect.width()
        view_height = view_rect.height()
        margin_bottom = 50 # Pixels from the bottom edge

        pos_x = (view_width - text_rect.width()) / 2
        pos_y = view_height - text_rect.height() - margin_bottom

        self.text_item.setPos(pos_x, pos_y)

        # Add to scene
        self.scene.addItem(self.text_item)
    # --- END NEW METHOD ---


    # --- NEW METHOD ---
    def clearText(self):
        """Removes the text overlay from the scene."""
        if self.text_item and self.text_item in self.scene.items():
            logger.debug("Clearing text item.")
            self.scene.removeItem(self.text_item)
            self.text_item = None
        self.current_text = None # Always clear the stored text
    # --- END NEW METHOD ---


    def clear_display(self):
        logger.info("Clearing display (images and text).")
        # --- MODIFIED: Ensure text is cleared too ---
        self.clearText()
        # --- END MODIFIED ---
        self.scene.clear()
        self.current_layers = []


    def resizeEvent(self, event):
        super().resizeEvent(event)
        # --- MODIFIED: Re-render both images and text ---
        logger.debug("Resize event, re-rendering content.")
        temp_text = self.current_text # Store text before display_images clears it
        self.display_images(self.current_layers)
        # If there was text, display_images would have called displayText.
        # However, to be certain, we can call it again.
        # Check if display_images already handled it:
        if self.text_item is None and temp_text:
             self.displayText(temp_text)
        elif self.text_item is not None:
             # It was likely redrawn, but let's ensure its position is updated
             self.displayText(self.current_text) # This will re-calculate pos

        # --- END MODIFIED ---


    def showEvent(self, event):
        super().showEvent(event)
        # --- MODIFIED: Ensure text is also rendered ---
        logger.debug("Show event, re-rendering content.")
        temp_text = self.current_text
        self.display_images(self.current_layers)
        if self.text_item is None and temp_text:
             self.displayText(temp_text)
        # --- END MODIFIED ---