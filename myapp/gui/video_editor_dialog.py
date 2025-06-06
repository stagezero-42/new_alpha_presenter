# myapp/gui/video_editor_dialog.py
import os
import logging
import shutil

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QPushButton, QLabel, QMessageBox, QCheckBox, QSlider, QSpinBox
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Signal, Qt
from PySide6.QtMultimedia import QMediaPlayer

from .widget_helpers import create_button
from .file_dialog_helpers import get_themed_open_filename
from ..utils.paths import get_media_path, get_media_file_path, get_icon_file_path
from ..utils.security import is_safe_filename_component

logger = logging.getLogger(__name__)


class VideoEditorDialog(QDialog):
    video_slide_data_updated = Signal(dict)

    def __init__(self, parent=None, slide_data=None, display_window=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Video Slide Details")
        self.setMinimumWidth(600)

        self.slide_data = slide_data or {}
        self.display_window = display_window
        self.media_path = get_media_path()

        self.selected_video_path = get_media_file_path(self.slide_data.get("video_path", "")) if self.slide_data.get(
            "video_path") else ""
        self.selected_thumbnail_path = get_media_file_path(
            self.slide_data.get("thumbnail_path", "")) if self.slide_data.get("thumbnail_path") else ""

        self._setup_ui()
        self._set_window_icon()
        self._load_data_to_ui()
        self.update_button_states()

        if self.display_window:
            self.display_window.video_state_changed.connect(self.update_button_states)

    def _set_window_icon(self):
        try:
            icon_path = get_icon_file_path("video.png")
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set VideoEditorDialog icon: {e}")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        file_group = QGroupBox("Video & Thumbnail Files")
        file_layout = QFormLayout(file_group)
        self.video_path_label = QLabel("No file selected.")
        browse_video_button = create_button("Browse...", on_click=self._browse_video)
        video_file_layout = QHBoxLayout()
        video_file_layout.addWidget(self.video_path_label, 1)
        video_file_layout.addWidget(browse_video_button)
        file_layout.addRow("Video File:", video_file_layout)

        self.thumb_path_label = QLabel("No file selected.")
        browse_thumb_button = create_button("Browse...", on_click=self._browse_thumbnail)
        thumb_file_layout = QHBoxLayout()
        thumb_file_layout.addWidget(self.thumb_path_label, 1)
        thumb_file_layout.addWidget(browse_thumb_button)
        file_layout.addRow("Thumbnail Image:", thumb_file_layout)
        main_layout.addWidget(file_group)

        playback_group = QGroupBox("Playback Options")
        playback_layout = QFormLayout(playback_group)
        self.autoplay_checkbox = QCheckBox("Auto-play video when slide is displayed")
        playback_layout.addRow(self.autoplay_checkbox)

        volume_layout = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_label = QLabel()
        self.volume_slider.valueChanged.connect(lambda val: self.volume_label.setText(f"{val}%"))
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        playback_layout.addRow("Volume:", volume_layout)

        self.intro_delay_spinbox = QSpinBox()
        self.intro_delay_spinbox.setRange(0, 300000)
        self.intro_delay_spinbox.setSuffix(" ms")
        self.intro_delay_spinbox.setToolTip("Wait this long before starting video playback.")
        playback_layout.addRow("Intro Delay:", self.intro_delay_spinbox)

        self.outro_delay_spinbox = QSpinBox()
        self.outro_delay_spinbox.setRange(0, 300000)
        self.outro_delay_spinbox.setSuffix(" ms (outro)")
        self.outro_delay_spinbox.setToolTip("After video ends, wait this long before advancing/looping.")
        playback_layout.addRow("Duration:", self.outro_delay_spinbox)

        self.loop_to_spinbox = QSpinBox()
        self.loop_to_spinbox.setRange(0, 999)
        playback_layout.addRow("Loop to Slide # (0 for none):", self.loop_to_spinbox)
        main_layout.addWidget(playback_group)

        button_layout = QHBoxLayout()
        self.toggle_display_button = create_button("Show Display", "show_display.png", on_click=self._toggle_display)
        self.play_pause_button = create_button("Preview", "play.png", on_click=self._toggle_preview_playback)
        self.stop_button = create_button("Stop", "stop.png", on_click=self._stop_preview)
        self.ok_button = create_button("OK", on_click=self._handle_ok)
        cancel_button = create_button("Cancel", on_click=self.reject)

        button_layout.addWidget(self.toggle_display_button)
        button_layout.addWidget(self.play_pause_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _load_data_to_ui(self):
        if self.slide_data.get("video_path"):
            self.video_path_label.setText(self.slide_data["video_path"])
        if self.slide_data.get("thumbnail_path"):
            self.thumb_path_label.setText(self.slide_data["thumbnail_path"])

        self.autoplay_checkbox.setChecked(self.slide_data.get("video_autoplay", True))
        volume = int(self.slide_data.get("video_volume", 0.8) * 100)
        self.volume_slider.setValue(volume)
        self.volume_label.setText(f"{volume}%")
        self.intro_delay_spinbox.setValue(self.slide_data.get("video_intro_delay_ms", 0))
        self.outro_delay_spinbox.setValue(self.slide_data.get("duration", 0))
        self.loop_to_spinbox.setValue(self.slide_data.get("loop_to_slide", 0))

    def update_button_states(self):
        self.ok_button.setEnabled(bool(self.selected_video_path and self.selected_thumbnail_path))
        preview_enabled = bool(self.selected_video_path and self.display_window)
        self.play_pause_button.setEnabled(preview_enabled)
        self.stop_button.setEnabled(preview_enabled)

        if self.display_window:
            self.toggle_display_button.setText("Hide Display" if self.display_window.isVisible() else "Show Display")

            # Update Play/Pause button based on player state, but only if it's the right video
            is_previewing_this_video = (self.display_window.current_video_path and
                                        os.path.basename(self.display_window.current_video_path) == os.path.basename(
                        self.selected_video_path))

            if is_previewing_this_video:
                state = self.display_window.get_playback_state()
                if state == QMediaPlayer.PlaybackState.PlayingState:
                    self.play_pause_button.setText("Pause")
                    self.play_pause_button.setIcon(QIcon(get_icon_file_path("pause.png")))
                else:  # Paused or Stopped
                    self.play_pause_button.setText("Play")
                    self.play_pause_button.setIcon(QIcon(get_icon_file_path("play.png")))
            else:  # Not previewing this video, or not previewing at all
                self.play_pause_button.setText("Preview")
                self.play_pause_button.setIcon(QIcon(get_icon_file_path("play.png")))

    def _toggle_display(self):
        if self.display_window:
            if self.display_window.isVisible():
                self.display_window.hide()
            else:
                self.display_window.showFullScreen()
            self.update_button_states()

    def _toggle_preview_playback(self):
        if not self.display_window or not self.selected_video_path: return

        if not self.display_window.isVisible():
            self.display_window.showFullScreen()
            self.update_button_states()

        # Check if the correct video is loaded for preview
        is_loaded = (self.display_window.current_video_path and
                     os.path.samefile(self.display_window.current_video_path, self.selected_video_path))

        if not is_loaded:
            # Load the video for the first time
            self.display_window.clear_display()
            self.display_window.set_volume(self.volume_slider.value() / 100.0)
            self.display_window.display_video(os.path.basename(self.selected_video_path))
            self.display_window.play_video()
        else:
            # Toggle play/pause
            if self.display_window.get_playback_state() == QMediaPlayer.PlaybackState.PlayingState:
                self.display_window.pause_video()
            else:
                self.display_window.play_video()

    def _stop_preview(self):
        if self.display_window:
            self.display_window.stop_video()
            # After stopping, clear the display to show the thumbnail again if desired, or just black
            self.display_window.clear_display()

    def _browse_video(self):
        file_path = get_themed_open_filename(self, "Select Video File", "", "Video Files (*.mp4 *.mov *.avi *.mkv)")
        if file_path:
            self.selected_video_path = file_path
            self.video_path_label.setText(os.path.basename(file_path))
        self.update_button_states()

    def _browse_thumbnail(self):
        file_path = get_themed_open_filename(self, "Select Thumbnail Image", "",
                                             "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.selected_thumbnail_path = file_path
            self.thumb_path_label.setText(os.path.basename(file_path))
        self.update_button_states()

    def _copy_file_to_media(self, source_path):
        if not source_path or not os.path.exists(source_path):
            return None, f"Source file does not exist: {source_path}"

        filename = os.path.basename(source_path)
        if not is_safe_filename_component(filename):
            return None, f"Filename contains invalid characters: {filename}"

        dest_path = get_media_file_path(filename)

        if os.path.exists(dest_path) and os.path.samefile(source_path, dest_path):
            return filename, None

        if not os.path.isabs(source_path):
            return filename, None

        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied '{filename}' to media directory.")
        except Exception as e:
            return None, f"Failed to copy '{filename}': {e}"

        return filename, None

    def _handle_ok(self):
        video_filename, error = self._copy_file_to_media(self.selected_video_path)
        if error:
            QMessageBox.critical(self, "Video File Error", error)
            return

        thumb_filename, error = self._copy_file_to_media(self.selected_thumbnail_path)
        if error:
            QMessageBox.critical(self, "Thumbnail File Error", error)
            return

        updated_slide_data = {
            "layers": [], "video_path": video_filename, "thumbnail_path": thumb_filename,
            "video_autoplay": self.autoplay_checkbox.isChecked(),
            "video_volume": self.volume_slider.value() / 100.0,
            "video_intro_delay_ms": self.intro_delay_spinbox.value(),
            "duration": self.outro_delay_spinbox.value(),
            "loop_to_slide": self.loop_to_spinbox.value(),
            "text_overlay": None
        }
        self.video_slide_data_updated.emit(updated_slide_data)
        self.accept()

    def closeEvent(self, event):
        # Stop any preview when the dialog is closed
        self._stop_preview()
        if self.display_window:
            self.display_window.video_state_changed.disconnect(self.update_button_states)
        super().closeEvent(event)