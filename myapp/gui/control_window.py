# control_window.py
import os
import json
from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox
from PySide6.QtGui import QShortcut, QKeySequence


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        self.setWindowTitle("Control Window")
        self.display_window = display_window
        self.playlist = []
        self.current_index = -1  # Start with no slide selected

        # Set up the UI
        central_widget = QWidget()
        layout = QVBoxLayout()

        self.load_button = QPushButton("Load Playlist")
        self.load_button.clicked.connect(self.load_playlist)
        layout.addWidget(self.load_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_slide)
        layout.addWidget(self.next_button)

        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.prev_slide)
        layout.addWidget(self.prev_button)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Set up keybindings
        QShortcut(QKeySequence("Right"), self, self.next_slide)
        QShortcut(QKeySequence("Left"), self, self.prev_slide)

    def load_playlist(self):
        """Load the playlist.json from the media_files folder."""
        playlist_path = os.path.join("..", "media_files", "playlist.json")
        print("Looking for playlist at:", os.path.abspath(playlist_path))
        if not os.path.exists(playlist_path):
            QMessageBox.warning(self, "Error", "Playlist file not found in media_files folder.")
            return
        try:
            with open(playlist_path, 'r') as f:
                data = json.load(f)
                self.playlist = data.get("slides", [])
                self.current_index = 0
                if self.playlist:
                    self.display_window.display_images(self.playlist[self.current_index]["layers"])
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.critical(self, "Error", f"Failed to load playlist: {e}")

    def next_slide(self):
        """Move to the next slide in the playlist."""
        if self.playlist and self.current_index < len(self.playlist) - 1:
            self.current_index += 1
            self.display_window.display_images(self.playlist[self.current_index]["layers"])

    def prev_slide(self):
        """Move to the previous slide in the playlist."""
        if self.playlist and self.current_index > 0:
            self.current_index -= 1
            self.display_window.display_images(self.playlist[self.current_index]["layers"])
