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

            <h2 id="slide_details_editor">Slide Details Editor (Edit Slide)</h2>
            <p>This dialog allows you to edit the fine details of an individual slide. It contains three main tabs: Image Layers, Text Overlay, and Audio Program.</p>
            <h3>Image Layers</h3>
            <ul>
                <li><b>Image Layers List:</b> Shows all images that make up the slide background. The bottom image in the list is the bottom layer.</li>
                <li><b>Add Image(s):</b> Opens a file dialog to select one or more images to add to the top of the layer stack.</li>
                <li><b>Remove Selected:</b> Removes the selected image from the layers.</li>
                <li><b>Reorder:</b> Drag and drop image names in the list to change their layering order.</li>
            </ul>
            <h3>Text Overlay</h3>
            <p>This tab controls the text displayed over the slide's images.</p>
            <ul>
                <li><b>Paragraph:</b> Select a pre-defined paragraph of text from the dropdown. To create or edit paragraphs, use the "Edit Text" button in the Playlist Editor.</li>
                <li><b>Start/End Sentence:</b> Choose which sentence(s) from the selected paragraph to display on this slide. Check "Use 'All' Sentences" to display the entire paragraph.</li>
                <li><b>Enable Sentence Timers:</b> If checked, each sentence will display for its pre-configured duration (set in the Text Editor). If unchecked, you must manually advance sentences with the Next/Prev buttons.</li>
                <li><b>Auto-Advance to Next Slide:</b> If sentence timers are enabled, checking this will automatically move to the next slide in the playlist after the last sentence has been displayed for its duration.</li>
                <li><b>Text Style:</b> Customize the font, size, color, background color, transparency, alignment, and position of the text overlay for this slide.</li>
            </ul>
            <h3>Audio Program</h3>
            <p>This tab controls the background audio for the slide.</p>
            <ul>
                <li><b>Audio Program:</b> Select a pre-defined audio program from the dropdown. To create or edit audio programs, use the "Edit Audio" button in the Playlist Editor.</li>
                <li><b>Intro Delay:</b> A delay in milliseconds before the audio program begins to play after the slide is displayed.</li>
                <li><b>Loop Audio Program:</b> If checked, the selected audio program will repeat as long as this slide is displayed.</li>
                <li><b>Outro Padding:</b> A delay in milliseconds after the audio program finishes, during which the slide remains displayed before any automatic looping or advancement occurs.</li>
                <li><b>Program Volume:</b> Adjust the volume of the audio program specifically for this slide.</li>
            </ul>
            
            <h2 id="video_slide_editor">Video Slide Editor</h2>
            <p>This dialog is for configuring video slides.</p>
            <ul>
                <li><b>Video File:</b> Click "Select File" to choose a video file for the slide. The path to the selected video will be displayed.</li>
                <li><b>Thumbnail:</b> The slide's thumbnail is shown here. By default, a frame from the video is used. Click "Set Custom Thumbnail" to select a different image file to represent the slide in the playlist editor. Click "Clear Custom" to revert to the default video frame thumbnail.</li>
                <li><b>Playback Options:</b>
                    <ul>
                        <li><b>Loop Video:</b> Check this to make the video repeat continuously as long as the slide is active.</li>
                        <li><b>Mute Video:</b> Check this to play the video without its own audio. This is useful if you are using a separate Audio Program for the slide.</li>
                        <li><b>Volume:</b> Adjust the video's intrinsic audio volume. This is independent of any separate Audio Program's volume.</li>
                    </ul>
                </li>
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