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
from .ui_updater import ControlWindowUIUpdater # <-- NEW IMPORT

logger = logging.getLogger(__name__)


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        logger.debug("Initializing ControlWindow...")
        self.setWindowTitle(f"Control Window v{__version__}")

        try:
            icon_name = "app_icon.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}", exc_info=True)

        self.display_window = display_window
        if not display_window: raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager()
        self.playlist = Playlist()
        self.paragraph_manager = ParagraphManager()
        self.playlist_validator = PlaylistValidator(self.paragraph_manager)
        self.text_controller = TextController(self.paragraph_manager, self.display_window)
        self.playlist_io = PlaylistIOHandler(self, self.settings_manager)
        self.ui_updater = ControlWindowUIUpdater(self) # <-- NEW

        self.current_index = -1
        self.is_displaying = False
        self._is_timer_for_initial_text_delay = False
        self.editor_window = None
        self.settings_window_instance = None
        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)
        self.indicator_icons = self._load_indicator_icons()

        self.setup_ui()
        setup_keybindings(self, self.settings_manager)
        self.ui_updater.update_all() # <-- Use UI Updater
        self.load_last_playlist()
        logger.debug("ControlWindow initialization complete.")

    def _load_indicator_icons(self):
        # ... (This method remains the same) ...
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
        # ... (This method remains the same, though it sets up the widgets
        #      that the UIUpdater will now control) ...
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
        self.ui_updater.update_issue_display([]) # <-- Use UI Updater


    # <-- REMOVED _update_issue_display -->
    # <-- REMOVED update_list_selection -->
    # <-- REMOVED update_show_clear_button_state -->
    # <-- REMOVED update_ui_state (in favour of individual calls or update_all) -->

    def populate_playlist_view(self):
        logger.debug("Populating playlist view...")
        self.playlist_view.clear()

        for i, slide_data in enumerate(self.playlist.get_slides()):
            text_overlay_info = slide_data.get("text_overlay")
            has_text = bool(text_overlay_info and text_overlay_info.get("paragraph_name"))

            composite_icon = create_composite_thumbnail(
                slide_data, i, self.indicator_icons, has_text_overlay=has_text
            )
            item = QListWidgetItem(composite_icon, "")
            # ... (Tooltip logic remains) ...
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
                    tooltip_parts.append(f"Loop to Slide {loop_target} (inactive due to 0s duration/delay)")

            if has_text:
                tooltip_parts.append(f"Text: {text_overlay_info.get('paragraph_name', 'N/A')}")

            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_view.addItem(item)

        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")
        issues = self.playlist_validator.validate(self.playlist)
        self.ui_updater.update_issue_display(issues) # <-- Use UI Updater

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
            self.current_index = -1; changed = (old_index != self.current_index)

        if changed:
            self.ui_updater.update_all() # <-- Use UI Updater
        return changed

    def _display_current_slide(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        self._is_timer_for_initial_text_delay = False

        slides = self.playlist.get_slides()
        if not (0 <= self.current_index < len(slides)):
            self.clear_display_screen(); return

        logger.info(f"Displaying slide {self.current_index + 1}.")
        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: self.clear_display_screen(); return

        self.is_displaying = True
        self.display_window.display_images(slide_data.get("layers", []))

        can_show_text, initial_delay = self.text_controller.load_slide_text(slide_data)

        if can_show_text:
            if initial_delay > 0:
                self._is_timer_for_initial_text_delay = True
                self.slide_timer.start(initial_delay)
            else:
                self.text_controller.show_first_sentence()
        else:
            slide_duration = slide_data.get("duration", 0)
            if slide_duration > 0: self.slide_timer.start(slide_duration)

        self.ui_updater.update_all() # <-- Use UI Updater

    def clear_display_screen(self):
        self.slide_timer.stop()
        self.text_controller.reset()
        self._is_timer_for_initial_text_delay = False
        if self.display_window: self.display_window.clear_display()
        self.is_displaying = False
        self.ui_updater.update_all() # <-- Use UI Updater

    def handle_show_clear_click(self):
        if self.is_displaying or self.text_controller.is_active():
            self.clear_display_screen()
        else:
            slides = self.playlist.get_slides()
            if not slides: QMessageBox.information(self, "No Playlist", "Load a playlist..."); return
            if not (0 <= self.current_index < len(slides)): self._set_slide_index(0)
            self._display_current_slide()

    def next_slide(self):
        if self.text_controller.is_active():
            if self.text_controller.show_next_sentence():
                self.ui_updater.update_all(); return
            else: self.text_controller.reset()

        slides = self.playlist.get_slides()
        if not slides or not (self.current_index < len(slides) - 1):
            self.ui_updater.update_all(); return

        self._set_slide_index(self.current_index + 1)
        self._display_current_slide()

    def prev_slide(self):
        if self.text_controller.is_active():
            if self.text_controller.show_prev_sentence():
                self.ui_updater.update_all(); return
            else: self.text_controller.reset()

        if not self.playlist.get_slides() or self.current_index <= 0:
            self.ui_updater.update_all(); return

        self._set_slide_index(self.current_index - 1)
        self._display_current_slide()

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if self._set_slide_index(index) or self.current_index == index:
                self._display_current_slide()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        self.slide_timer.stop()
        if current_item:
            self._set_slide_index(current_item.data(Qt.ItemDataRole.UserRole))
        else:
            self._set_slide_index(-1); self.clear_display_screen()

    def auto_advance_or_loop_slide(self):
        if self._is_timer_for_initial_text_delay:
            self._is_timer_for_initial_text_delay = False
            if self.text_controller.is_active(): self.text_controller.show_first_sentence()
            return

        if not self.is_displaying or self.text_controller.is_active(): return

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data: self.clear_display_screen(); return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)

        if loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                self._set_slide_index(loop_target_0_based)
                self._display_current_slide(); return

        if self.current_index < num_slides - 1: self.next_slide()
        else: self.clear_display_screen()

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
        self.ui_updater.update_all() # <-- Use UI Updater

    def load_playlist_dialog(self):
        file_path = self.playlist_io.prompt_load_playlist()
        if file_path: self._load_and_update_playlist(file_path)

    def load_last_playlist(self):
        file_path = self.playlist_io.get_last_playlist_path()
        if file_path: self._load_and_update_playlist(file_path)
        else: self.populate_playlist_view(); self.clear_display_screen(); self.ui_updater.update_all()

    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(self.display_window, self.playlist, self)
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else: self.editor_window.activateWindow(); self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        self._load_and_update_playlist(saved_playlist_path)

    def open_settings_window(self):
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            self.settings_window_instance = SettingsWindow(self)
            self.settings_window_instance.show()
        else: self.settings_window_instance.activateWindow(); self.settings_window_instance.raise_()

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
        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close(): event.ignore(); return
        if self.settings_window_instance and self.settings_window_instance.isVisible():
            self.settings_window_instance.close()
        if self.display_window and self.display_window.isVisible():
            self.display_window.close()
        QCoreApplication.instance().quit()
        event.accept()