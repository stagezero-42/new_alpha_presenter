# myapp/gui/display_window.py
import os
from PySide6.QtWidgets import QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor  # Added QBrush, QColor
from PySide6.QtCore import Qt, QRectF


class DisplayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Display Window")

        # Set up the graphics view and scene
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)

        # --- NEW: Set Black Background ---
        self.view.setBackgroundBrush(QBrush(QColor(0, 0, 0)))  # Set background to black
        self.view.setStyleSheet("border: 0px")  # Ensure no border/padding
        # --- END NEW ---

        # Improve rendering quality
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.setCentralWidget(self.view)

        # Remove window frame for true full-screen
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.media_base_path = ""
        self.current_layers = []  # Store current layers for redraw on resize

    def display_images(self, image_relative_paths, media_base_path):
        """Display a list of images with layering."""
        self.scene.clear()  # Clear previous items
        self.media_base_path = media_base_path
        self.current_layers = image_relative_paths  # Store for resize

        if not image_relative_paths:
            print("No images to display for the current slide.")
            return

        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty():
            view_rect = self.rect()
            if view_rect.isEmpty():
                print("View or window rect is empty, cannot determine size for scaling images.")
                return

        for i, rel_path in enumerate(image_relative_paths):
            full_path = os.path.join(self.media_base_path, rel_path)

            if not os.path.exists(full_path):
                error_msg = f"Image not found: {full_path}"
                print(error_msg)
                continue

            pixmap = QPixmap(full_path)
            if pixmap.isNull():
                error_msg = f"Failed to load image (or image is invalid): {full_path}"
                print(error_msg)
                continue

            pixmap_scaled = pixmap.scaled(view_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)

            item = QGraphicsPixmapItem(pixmap_scaled)

            item_x = (view_rect.width() - pixmap_scaled.width()) / 2
            item_y = (view_rect.height() - pixmap_scaled.height()) / 2
            item.setPos(item_x, item_y)

            item.setZValue(i)
            self.scene.addItem(item)

        self.scene.setSceneRect(QRectF(view_rect))

    def clear_display(self):
        """Clears all items from the display scene."""
        self.scene.clear()
        self.current_layers = []
        print("Display cleared.")

    def resizeEvent(self, event):
        """Handle window resize events to re-scale and re-center images."""
        super().resizeEvent(event)
        # Re-display current layers on resize to ensure scaling is correct
        if self.current_layers and self.media_base_path:
            print(f"DisplayWindow resized. Re-displaying current layers.")
            self.display_images(self.current_layers, self.media_base_path)
        else:
            print(f"DisplayWindow resized to: {event.size()}")

    def showEvent(self, event):
        """Handle window show events, especially for initial sizing."""
        super().showEvent(event)
        print(f"DisplayWindow shown with geometry: {self.geometry()}")
        # Re-display if layers were set before window was sized
        if self.current_layers and self.media_base_path:
            self.display_images(self.current_layers, self.media_base_path)

