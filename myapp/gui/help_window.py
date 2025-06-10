# myapp/gui/help_window.py
import os
import logging
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
from PySide6.QtGui import QIcon
from ..utils.paths import get_icon_file_path

logger = logging.getLogger(__name__)


class HelpWindow(QDialog):
    def __init__(self, parent=None, anchor=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        try:
            icon_path = get_icon_file_path("help.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set HelpWindow icon: {e}", exc_info=True)

        self.setGeometry(150, 150, 600, 500)

        main_layout = QVBoxLayout(self)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setHtml(self.get_help_content())

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        main_layout.addWidget(self.text_browser)
        main_layout.addWidget(close_button)

        self.setLayout(main_layout)

        if anchor:
            self.text_browser.scrollToAnchor(anchor)

    def get_help_content(self):
        """Returns the HTML content for the help window."""
        return """
            <h1>Alpha Presenter Help</h1>

            <h2 id="control_window">Control Window</h2>
            <p>This is the main window for controlling the presentation.</p>
            <ul>
                <li><b>Load Playlist:</b> Opens a dialog to load a .json playlist file.</li>
                <li><b>Edit Playlist:</b> Opens the Playlist Editor window to modify the current playlist.</li>
                <li><b>Settings:</b> Opens the application settings.</li>
                <li><b>Playlist View:</b> Shows thumbnails of all slides. Double-click to jump to and display a slide.</li>
                <li><b>Show/Clear:</b> Starts displaying the selected slide or clears the display screen if something is showing.</li>
                <li><b>Show/Hide Display:</b> Toggles the visibility of the main output window.</li>
                <li><b>Prev/Next:</b> Navigates between slides or sentences in a text overlay.</li>
            </ul>

            <h2 id="playlist_editor">Playlist Editor</h2>
            <p>This window is used to create and modify playlists.</p>
            <ul>
                <li><b>New/Load/Save/Save As:</b> Standard file operations for playlists.</li>
                <li><b>Add Image Slide:</b> Adds a new slide for still images.</li>
                <li><b>Add/Edit Video Slide:</b> Adds a new video-based slide or edits the selected one.</li>
                <li><b>Duplicate Slide:</b> Creates a copy of the selected slide.</li>
                <li><b>Edit Details:</b> Opens a dialog to edit the properties of the selected slide (images, duration, audio, text overlay, etc.).</li>
                <li><b>Edit Text/Audio Programs:</b> Opens dedicated editors for managing text paragraphs and audio programs that can be used across multiple slides.</li>
                <li><b>Preview Slide:</b> Shows the selected slide on the display window.</li>
                <li><b>Remove Slide:</b> Deletes the currently selected slide.</li>
            </ul>

           <h2 id="settings_window">Application Settings</h2>
            <p>This window allows you to configure default paths and keybindings.</p>
            <ul>
                <li><b>Default Paths:</b> Set the default folders where the application will look for Playlists, Media (images/videos), and Text files.</li>
                <li><b>Keybindings:</b> Customize the keyboard shortcuts for various application actions.</li>
            </ul>
            <h3 id="keybindings">Default Keybindings</h3>
            <p>
            <ul>
                <li><b>Ctrl+L:</b> Load Playlist</li>
                <li><b>Ctrl+E:</b> Open Playlist Editor</li>
                <li><b>Ctrl+Q:</b> Quit Application</li>
                <li><b>Left Arrow:</b> Previous Slide/Sentence</li>
                <li><b>Right Arrow:</b> Next Slide/Sentence</li>
                <li><b>Spacebar:</b> Next Slide/Sentence</li>
                <li><b>Escape:</b> Clear Display Screen</li>
            </ul>
            </p>
        """