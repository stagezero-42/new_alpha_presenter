# myapp/media/media_renderer.py
import os
import logging  # Import logging
from PySide6.QtWidgets import QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QIcon
from PySide6.QtCore import Qt, QRectF
from ..utils.paths import get_media_file_path, get_icon_file_path

logger = logging.getLogger(__name__)  # Get logger for this module

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
        logger.debug("MediaRenderer initialized.")

    def display_images(self, image_filenames):
        """Display a list of images with layering.
           image_filenames: List of *just filenames*.
        """
        logger.debug(f"Displaying images: {image_filenames}")
        self.scene.clear()
        self.current_layers = image_filenames

        if not image_filenames:
            logger.info("No images to display for the current slide.")
            return

        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty(): view_rect = self.rect()
        if view_rect.isEmpty():
            logger.warning("View or window rect is empty, cannot scale images.")
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
            item.setZValue(i)
            self.scene.addItem(item)

        self.scene.setSceneRect(QRectF(view_rect))
        logger.debug("Image display complete.")

    def clear_display(self):
        logger.info("Clearing display.")
        self.scene.clear()
        self.current_layers = []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_layers:
            self.display_images(self.current_layers)

    def showEvent(self, event):
        super().showEvent(event)
        if self.current_layers:
            self.display_images(self.current_layers)