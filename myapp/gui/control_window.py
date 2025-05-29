# myapp/gui/control_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QListWidget, QListWidgetItem, QHBoxLayout, QApplication,
    QListView, QAbstractItemView, QLabel
)
from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

# Local Imports
from .playlist_editor import PlaylistEditorWindow
from .settings_window import SettingsWindow
from ..playlist.playlist import Playlist
from ..text.paragraph_manager import ParagraphManager
from ..utils.paths import get_icon_file_path
from ..settings.settings_manager import SettingsManager
from myapp.settings.key_bindings import setup_keybindings
from myapp import __version__
from .thumbnail_generator import create_composite_thumbnail, get_thumbnail_size, get_list_widget_height
from .slide_timer import SlideTimer
from .widget_helpers import create_button
from .playlist_validator import PlaylistValidator
from .text_controller import TextController
from .playlist_io_handler import PlaylistIOHandler
from .ui_updater import ControlWindowUIUpdater

logger = logging.getLogger(__name__)


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        logger.debug("Initializing ControlWindow...")
        self.setWindowTitle(f"Control Window v{__version__}")

        try:
            icon_name = "app_icon.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}")

        self.display_window = display_window
        if not display_window: raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager()
        self.playlist = Playlist()
        self.paragraph_manager = ParagraphManager()
        self.playlist_validator = PlaylistValidator(self.paragraph_manager)
        self.text_controller = TextController(self.paragraph_manager, self.display_window)
        self.playlist_io = PlaylistIOHandler(self, self.settings_manager)
        self.ui_updater = ControlWindowUIUpdater(self)

        self.current_index = -1
        self.is_displaying = False  # True if images are shown
        self._is_timer_for_initial_text_delay = False  # For the main SlideTimer

        self.editor_window = None
        self.settings_window_instance = None

        self.slide_timer = SlideTimer(self)  # For initial text delay OR slide duration
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)

        self.text_controller.finished_and_should_advance_slide.connect(self._handle_text_finished_advance)

        self.indicator_icons = self._load_indicator_icons()
        self.setup_ui()
        setup_keybindings(self, self.settings_manager)
        self.ui_updater.update_all()
        self.load_last_playlist()
        logger.debug("ControlWindow initialization complete.")

    def _load_indicator_icons(self):
        logger.debug("Loading indicator icons...")
        icons = {}
        icon_files = {
            "slide": "slide_icon.png",
            "timer": "timer_icon.png",
            "loop": "loop_icon.png",
            "text": "text.png"
        }
        size = 16
        for name, filename in icon_files.items():
            try:
                path = get_icon_file_path(filename)
                if not path or not os.path.exists(path):
                    logger.warning(f"Indicator icon file not found: {filename}")
                    icons[name] = QPixmap()
                    continue
                pixmap = QPixmap(path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                if pixmap.isNull():
                    logger.warning(f"Failed to load or scale indicator icon '{filename}'.")
                    icons[name] = QPixmap()
                else:
                    icons[name] = pixmap
            except Exception as e:
                logger.critical(f"Unexpected error loading indicator icon '{filename}': {e}", exc_info=True)
                icons[name] = QPixmap()
        return icons

    def setup_ui(self):
        logger.debug("Setting up ControlWindow UI...")
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        top_buttons_layout = QHBoxLayout()
        self.load_button = create_button(" Load", "load.png", "Load a playlist (Ctrl+L)", self.load_playlist_dialog)
        self.edit_button = create_button(" Edit", "edit.png", "Open the Playlist Editor (Ctrl+E)",
                                         self.open_playlist_editor)
        self.settings_button = create_button(" Settings", "settings.png", "Open Application Settings",
                                             self.open_settings_window)

        self.issue_label = QLabel("")
        self.issue_label.setStyleSheet("color: red; font-weight: bold;")
        self.issue_icon_widget = QWidget()
        self.issue_icon_layout = QHBoxLayout(self.issue_icon_widget)
        self.issue_icon_layout.setContentsMargins(0, 0, 0, 0)
        self.issue_icon_layout.setSpacing(2)

        self.close_button = create_button(" Close", "close.png", "Close the application (Ctrl+Q)",
                                          self.close_application)

        top_buttons_layout.addWidget(self.load_button)
        top_buttons_layout.addWidget(self.edit_button)
        top_buttons_layout.addWidget(self.settings_button)
        top_buttons_layout.addStretch()
        top_buttons_layout.addWidget(self.issue_label)
        top_buttons_layout.addWidget(self.issue_icon_widget)
        top_buttons_layout.addWidget(self.close_button)
        main_layout.addLayout(top_buttons_layout)

        self.playlist_view = QListWidget()
        self.playlist_view.setViewMode(QListView.ViewMode.IconMode)
        self.playlist_view.setFlow(QListView.Flow.LeftToRight)
        self.playlist_view.setMovement(QListView.Movement.Static)
        self.playlist_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.playlist_view.setWrapping(False)
        self.playlist_view.setIconSize(get_thumbnail_size())
        self.playlist_view.setFixedHeight(get_list_widget_height())
        self.playlist_view.setSpacing(5)
        self.playlist_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlist_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.playlist_view.currentItemChanged.connect(self.handle_list_selection)
        self.playlist_view.itemDoubleClicked.connect(self.go_to_selected_slide_from_list)
        main_layout.addWidget(self.playlist_view)

        playback_buttons_layout = QHBoxLayout()
        self.show_clear_button = QPushButton()
        self.show_clear_button.clicked.connect(self.handle_show_clear_click)

        self.toggle_display_button = create_button("Show Display", "show_display.png",
                                                   "Show or Hide the Display Window",
                                                   self.toggle_display_window_visibility)

        self.prev_button = create_button(" Prev", "previous.png", "Previous slide (Arrow Keys, Page Up/Down)",
                                         self.prev_slide)
        self.next_button = create_button(" Next", "next.png", "Next slide (Arrow Keys, Page Up/Down)", self.next_slide)

        playback_buttons_layout.addWidget(self.show_clear_button)
        playback_buttons_layout.addWidget(self.toggle_display_button)
        playback_buttons_layout.addStretch()
        playback_buttons_layout.addWidget(self.prev_button)
        playback_buttons_layout.addWidget(self.next_button)
        main_layout.addLayout(playback_buttons_layout)

        self.setCentralWidget(central_widget)
        self.resize(700, 350)
        logger.debug("ControlWindow UI setup complete.")
        self.ui_updater.update_issue_display([])

    def _handle_text_finished_advance(self):
        logger.info("TextController signaled to advance to next slide.")
        self.text_controller.reset()  # Reset text state before moving

        slides = self.playlist.get_slides()
        # Check if there is a next slide
        if self.current_index < len(slides) - 1:
            self._set_slide_index(self.current_index + 1)
            self._display_current_slide()
        else:  # It was the last slide
            logger.info("Text finished on the last slide, no next slide to auto-advance to.")
            # Potentially clear display or just stop, current clear_display_screen might be too much.
            # For now, let text controller handle its own clearing, just update UI.
            self.is_displaying = True  # Keep images if any
            if self.display_window: self.display_window.clearText()  # Clear only text
            self.text_controller.reset()  # Ensure it's fully reset

        self.ui_updater.update_all()

    def populate_playlist_view(self):
        logger.debug("Populating playlist view...")
        self.playlist_view.clear()

        for i, slide_data in enumerate(self.playlist.get_slides()):
            # Robustly get text_overlay_info, ensuring it's a dict for safer access
            text_overlay_info = slide_data.get("text_overlay")
            if not isinstance(text_overlay_info, dict):
                text_overlay_info = {}  # Default to empty if None or not a dict

            has_text = bool(text_overlay_info.get("paragraph_name"))

            composite_icon = create_composite_thumbnail(
                slide_data, i, self.indicator_icons, has_text_overlay=has_text
            )
            item = QListWidgetItem(composite_icon, "")

            tooltip_parts = [f"Slide {i + 1}"]
            duration = slide_data.get("duration", 0)
            loop_target = slide_data.get("loop_to_slide", 0)

            if has_text:
                tooltip_parts.append(f"Initial Text Delay: {duration}s")
            elif duration > 0:
                tooltip_parts.append(f"Plays for: {duration}s")
            else:
                tooltip_parts.append("Manual advance")

            if loop_target > 0:
                if duration > 0:
                    tooltip_parts.append(f"Loops to: Slide {loop_target}")
                else:
                    tooltip_parts.append(f"Loop to Slide {loop_target} (inactive)")

            if has_text:
                tooltip_parts.append(f"Text: {text_overlay_info.get('paragraph_name', 'N/A')}")
                if text_overlay_info.get("sentence_timing_enabled"):
                    tooltip_parts.append("Timed Sentences")
                    if text_overlay_info.get("auto_advance_slide"):
                        tooltip_parts.append("Auto->Next Slide")

            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_view.addItem(item)

        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")
        issues = self.playlist_validator.validate(self.playlist)
        self.ui_updater.update_issue_display(issues)

    def _set_slide_index(self, new_index):
        slides = self.playlist.get_slides()
        num_slides = len(slides)
        old_index = self.current_index
        changed = False

        if not slides:
            if self.current_index != -1: self.current_index = -1; changed = True
        elif 0 <= new_index < num_slides:
            if self.current_index != new_index: self.current_index = new_index; changed = True
        elif not (0 <= self.current_index < num_slides):
            self.current_index = -1;
            changed = (old_index != self.current_index)

        if changed:
            self.ui_updater.update_all()
        return changed

    def _display_current_slide(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        self._is_timer_for_initial_text_delay = False

        slides = self.playlist.get_slides()
        if not (0 <= self.current_index < len(slides)):
            self.clear_display_screen();
            return

        logger.info(f"Displaying slide {self.current_index + 1}.")
        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data:
            logger.warning(f"Slide data is None for valid index {self.current_index}, clearing.")
            self.clear_display_screen();
            return

        self.is_displaying = True
        self.display_window.display_images(slide_data.get("layers", []))

        # TextController's load_slide_text will handle getting text_overlay and its settings
        can_show_text, initial_delay = self.text_controller.load_slide_text(slide_data)

        if can_show_text:
            if initial_delay > 0:
                logger.info(f"Starting initial text delay of {initial_delay}s for slide {self.current_index + 1}.")
                self._is_timer_for_initial_text_delay = True
                self.slide_timer.start(initial_delay)
            else:
                logger.info("No initial text delay. Showing first sentence immediately.")
                self.text_controller.show_first_sentence()
        else:
            slide_duration = slide_data.get("duration", 0)
            if slide_duration > 0:
                logger.debug(
                    f"Starting slide duration timer of {slide_duration}s for slide {self.current_index + 1} (no text or text failed).")
                self.slide_timer.start(slide_duration)

        self.ui_updater.update_all()

    def clear_display_screen(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        self._is_timer_for_initial_text_delay = False
        if self.display_window: self.display_window.clear_display()
        self.is_displaying = False
        self.ui_updater.update_all()

    def handle_show_clear_click(self):
        if self.is_displaying or self.text_controller.is_active():
            self.clear_display_screen()
        else:
            slides = self.playlist.get_slides()
            if not slides: QMessageBox.information(self, "No Playlist", "Load a playlist..."); return
            if not (0 <= self.current_index < len(slides)): self._set_slide_index(0)
            self._display_current_slide()

    def next_slide(self):
        logger.debug("ControlWindow: next_slide called")
        self.text_controller.stop_sentence_timer()

        if self.text_controller.is_active():
            if self.text_controller.show_next_sentence():  # Tries to advance text
                self.ui_updater.update_all();
                return  # Text advanced, stay on slide
            else:  # Text was active but finished (or couldn't advance)
                self.text_controller.reset()  # Ensure it's fully reset before slide change

        # Proceed to change slide
        slides = self.playlist.get_slides()
        if not slides or not (self.current_index < len(slides) - 1):
            logger.info("Cannot go next: No more slides or playlist empty.")
            self.ui_updater.update_all();
            return  # Update UI (e.g., disable next button)

        self._set_slide_index(self.current_index + 1)
        self._display_current_slide()

    def prev_slide(self):
        logger.debug("ControlWindow: prev_slide called")
        self.text_controller.stop_sentence_timer()

        if self.text_controller.is_active():
            if self.text_controller.show_prev_sentence():  # Tries to go to previous sentence
                self.ui_updater.update_all();
                return  # Text moved back, stay on slide
            else:  # At start of text or text not active for prev
                self.text_controller.reset()  # Reset before slide change

        # Proceed to change to previous slide
        if not self.playlist.get_slides() or self.current_index <= 0:
            logger.info("Cannot go previous: No slides or already at the start.")
            self.ui_updater.update_all();
            return

        self._set_slide_index(self.current_index - 1)
        self._display_current_slide()

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            # Only display if index actually changed or if it's re-selected and not showing
            if self.current_index != index or not (self.is_displaying or self.text_controller.is_active()):
                if self._set_slide_index(index):  # If index changed
                    self._display_current_slide()
            elif self.current_index == index:  # If same slide is double-clicked, ensure it's shown
                self._display_current_slide()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        logger.debug(
            f"List selection changed. Current: {current_item.data(Qt.ItemDataRole.UserRole) if current_item else 'None'}")
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()

        if current_item:
            new_idx = current_item.data(Qt.ItemDataRole.UserRole)
            if self.current_index != new_idx:  # Only reset display state if index actually changes
                self.is_displaying = False
                self.text_controller.reset()
                if self.display_window: self.display_window.clearText()
            self._set_slide_index(new_idx)  # This will call ui_updater.update_all()
        else:
            self._set_slide_index(-1)
            self.clear_display_screen()  # This will also call ui_updater.update_all()
        # ui_updater.update_all() is called by _set_slide_index or clear_display_screen

    def auto_advance_or_loop_slide(self):
        logger.debug(f"Main SlideTimer timeout. For initial text delay: {self._is_timer_for_initial_text_delay}")

        if self._is_timer_for_initial_text_delay:
            self._is_timer_for_initial_text_delay = False
            if self.text_controller.is_active():  # is_active means text was loaded
                logger.info("Initial text delay timer expired. Showing first sentence.")
                self.text_controller.show_first_sentence()
            else:
                logger.warning(
                    "Initial text delay timer expired, but no text active in TextController (e.g. paragraph missing).")
            return

            # If text is active and handling its own timing, this timer was for slide duration and should be ignored for text.
        if self.text_controller.is_active() and self.text_controller._sentence_timing_enabled:
            logger.debug("Slide duration timer fired, but text controller is active with sentence timing. Ignoring.")
            return

        if not self.is_displaying:  # If images are not showing, this timer is irrelevant.
            logger.warning("Slide duration timer fired but main display (is_displaying) is false. Stopping.")
            return

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: self.clear_display_screen(); return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)

        if loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                logger.info(f"Slide timer: Looping to slide {loop_target_1_based}.")
                self._set_slide_index(loop_target_0_based)
                self._display_current_slide();
                return
            else:
                logger.warning(f"Slide timer: Invalid loop target ({loop_target_1_based}). Advancing if possible.")

        if self.current_index < num_slides - 1:
            logger.info("Slide timer: Auto-advancing to next slide.")
            self.next_slide()
        else:
            logger.info("Slide timer: Expired on last slide, no loop. Clearing display.")
            self.clear_display_screen()

    def _load_and_update_playlist(self, file_path: str):
        self.clear_display_screen()
        try:
            self.playlist.load(file_path)
            self.settings_manager.set_current_playlist(file_path)
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist()
            self.settings_manager.set_current_playlist(None)

        self.populate_playlist_view()
        self._set_slide_index(0 if self.playlist.get_slides() else -1)
        self.ui_updater.update_all()

    def load_playlist_dialog(self):
        file_path = self.playlist_io.prompt_load_playlist()
        if file_path: self._load_and_update_playlist(file_path)

    def load_last_playlist(self):
        file_path = self.playlist_io.get_last_playlist_path()
        if file_path:
            self._load_and_update_playlist(file_path)
        else:
            self.populate_playlist_view(); self.clear_display_screen(); self.ui_updater.update_all()

    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(self.display_window, self.playlist, self)
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow(); self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        self._load_and_update_playlist(saved_playlist_path)

    def open_settings_window(self):
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            self.settings_window_instance = SettingsWindow(self)
            self.settings_window_instance.show()
        else:
            self.settings_window_instance.activateWindow(); self.settings_window_instance.raise_()

    def toggle_display_window_visibility(self):
        if self.display_window:
            if self.display_window.isVisible():
                self.display_window.hide()
                self.toggle_display_button.setText("Show Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png")))
            else:
                screens = QApplication.instance().screens()
                if screens:
                    target = screens[1] if len(screens) > 1 else screens[0]
                    self.display_window.setGeometry(target.geometry())
                self.display_window.showFullScreen()
                self.toggle_display_button.setText("Hide Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("hide_display.png")))

    def close_application(self):
        self.close()

    def closeEvent(self, event):
        self.slide_timer.stop()
        self.text_controller.stop_sentence_timer()  # Ensure this is also stopped

        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close(): event.ignore(); return
        if self.settings_window_instance and self.settings_window_instance.isVisible():
            self.settings_window_instance.close()
        if self.display_window and self.display_window.isVisible():
            self.display_window.close()
        QCoreApplication.instance().quit()
        event.accept()