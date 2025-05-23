# display_window.py
import os
from PySide6.QtWidgets import QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt


class DisplayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Display Window")

        # Set up the graphics view and scene
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)

        # Remove window frame for true full-screen
        self.setWindowFlags(Qt.FramelessWindowHint)

    def display_images(self, image_paths):
        """Display a list of images with layering from the media_files folder."""
        self.scene.clear()
        view_rect = self.view.viewport().rect()

        for i, path in enumerate(image_paths):
            full_path = os.path.join("media_files", path)
            if not os.path.exists(full_path):
                print(f"Image not found: {full_path}")
                continue
            pixmap = QGraphicsPixmapItem.pixmap(QGraphicsPixmapItem(full_path))
            if pixmap.isNull():
                print(f"Failed to load image: {full_path}")
                continue
            # Scale image to fit the view while maintaining aspect ratio
            pixmap_scaled = pixmap.scaled(view_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item = QGraphicsPixmapItem(pixmap_scaled)
            # Center the image
            item.setPos((view_rect.width() - pixmap_scaled.width()) / 2,
                        (view_rect.height() - pixmap_scaled.height()) / 2)
            self.scene.addItem(item)
            item.setZValue(i)  # Higher z-value appears on top