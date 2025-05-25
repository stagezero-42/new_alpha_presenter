# myapp/media/media_renderer.py
import os
from PySide6.QtWidgets import QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor
from PySide6.QtCore import Qt, QRectF
# No change needed to paths here, it receives the full path or base path

class MediaRenderer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Display Window")

        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)

        self.view.setBackgroundBrush(QBrush(QColor(0, 0, 0)))
        self.view.setStyleSheet("border: 0px")

        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.setCentralWidget(self.view)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.media_base_path = "" # This will be assets/media
        self.current_layers = []

    def display_images(self, image_filenames, media_base_path):
        """Display a list of images with layering.
           image_filenames: List of *just filenames*.
           media_base_path: The path to the central 'assets/media' folder.
        """
        self.scene.clear()
        self.media_base_path = media_base_path
        self.current_layers = image_filenames

        if not image_filenames:
            print("No images to display for the current slide.")
            return

        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty(): view_rect = self.rect()
        if view_rect.isEmpty():
            print("View or window rect is empty, cannot scale images.")
            return

        for i, filename in enumerate(image_filenames):
            # Construct full path using the base media path
            full_path = os.path.join(self.media_base_path, filename)

            if not os.path.exists(full_path):
                print(f"Image not found: {full_path}")
                continue

            pixmap = QPixmap(full_path)
            if pixmap.isNull():
                print(f"Failed to load image: {full_path}")
                continue

            pixmap_scaled = pixmap.scaled(view_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            item = QGraphicsPixmapItem(pixmap_scaled)
            item.setPos((view_rect.width() - pixmap_scaled.width()) / 2,
                        (view_rect.height() - pixmap_scaled.height()) / 2)
            item.setZValue(i)
            self.scene.addItem(item)

        self.scene.setSceneRect(QRectF(view_rect))

    def clear_display(self):
        self.scene.clear()
        self.current_layers = []
        print("Display cleared.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_layers and self.media_base_path:
            self.display_images(self.current_layers, self.media_base_path)

    def showEvent(self, event):
        super().showEvent(event)
        if self.current_layers and self.media_base_path:
            self.display_images(self.current_layers, self.media_base_path)