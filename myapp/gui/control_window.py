# myapp/gui/control_window.py
import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QListWidget, QListWidgetItem, QHBoxLayout, QApplication,
    QListView, QAbstractItemView, QLabel  # Added QLabel
)
from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

# Local Imports
from .file_dialog_helpers import get_themed_open_filename
from .playlist_editor import PlaylistEditorWindow
from .settings_window import SettingsWindow
from ..playlist.playlist import Playlist
from ..text.paragraph_manager import ParagraphManager
from ..utils.paths import get_icon_file_path, get_playlists_path
from ..settings.settings_manager import SettingsManager
from myapp.settings.key_bindings import setup_keybindings
from myapp import __version__
from .thumbnail_generator import (
    create_composite_thumbnail,
    get_thumbnail_size,
    get_list_widget_height
)
from .slide_timer import SlideTimer
from .widget_helpers import create_button

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
            else:
                logger.warning(f"Window icon '{icon_name}' not found.")
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}", exc_info=True)

        self.display_window = display_window
        if not display_window:
            logger.critical("DisplayWindow instance must be provided.")
            raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager()
        self.playlist = Playlist()
        self.paragraph_manager = ParagraphManager()
        self.current_index = -1
        self.is_displaying = False

        self.current_paragraph_data = None
        self.current_sentence_index = -1
        self.text_start_index = -1
        self.text_end_index = -1
        self._is_timer_for_initial_text_delay = False

        self.editor_window = None
        self.settings_window_instance = None

        self.slide_timer = SlideTimer(self)
        self.slide_timer.timeout_action_required.connect(self.auto_advance_or_loop_slide)
        self.indicator_icons = self._load_indicator_icons()

        self.setup_ui()  # Sets up UI elements including issue label
        setup_keybindings(self, self.settings_manager)
        self.update_ui_state()
        self.load_last_playlist()  # This will call _update_playlist_issues
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

        # Top buttons layout
        top_buttons_layout = QHBoxLayout()
        self.load_button = create_button(" Load", "load.png", "Load a playlist (Ctrl+L)", self.load_playlist_dialog)
        self.edit_button = create_button(" Edit", "edit.png", "Open the Playlist Editor (Ctrl+E)",
                                         self.open_playlist_editor)
        self.settings_button = create_button(" Settings", "settings.png", "Open Application Settings",
                                             self.open_settings_window)

        # --- NEW: Issue Reporting UI ---
        self.issue_label = QLabel("")
        self.issue_label.setStyleSheet("color: red; font-weight: bold;")
        self.issue_icon_widget = QWidget()  # Container for icons
        self.issue_icon_layout = QHBoxLayout(self.issue_icon_widget)
        self.issue_icon_layout.setContentsMargins(0, 0, 0, 0)
        self.issue_icon_layout.setSpacing(2)
        # --- END NEW ---

        self.close_button = create_button(" Close", "close.png", "Close the application (Ctrl+Q)",
                                          self.close_application)

        top_buttons_layout.addWidget(self.load_button)
        top_buttons_layout.addWidget(self.edit_button)
        top_buttons_layout.addWidget(self.settings_button)
        top_buttons_layout.addStretch()
        # --- NEW: Add issue widgets ---
        top_buttons_layout.addWidget(self.issue_label)
        top_buttons_layout.addWidget(self.issue_icon_widget)
        # --- END NEW ---
        top_buttons_layout.addWidget(self.close_button)
        main_layout.addLayout(top_buttons_layout)

        self.playlist_view = QListWidget()
        # ... (playlist_view setup remains the same) ...
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

        # Bottom playback controls
        playback_buttons_layout = QHBoxLayout()
        self.show_clear_button = QPushButton()  # Text/Icon set in update_show_clear_button_state
        self.show_clear_button.clicked.connect(self.handle_show_clear_click)

        # --- MOVED: Toggle Display Button ---
        self.toggle_display_button = create_button("Show Display", "show_display.png",
                                                   "Show or Hide the Display Window",
                                                   self.toggle_display_window_visibility)
        # --- END MOVED ---

        self.prev_button = create_button(" Prev", "previous.png", "Previous slide (Arrow Keys, Page Up/Down)",
                                         self.prev_slide)
        self.next_button = create_button(" Next", "next.png", "Next slide (Arrow Keys, Page Up/Down)", self.next_slide)

        playback_buttons_layout.addWidget(self.show_clear_button)
        # --- ADDED: Toggle Display Button Here ---
        playback_buttons_layout.addWidget(self.toggle_display_button)
        # --- END ADDED ---
        playback_buttons_layout.addStretch()  # Pushes Prev/Next to the right
        playback_buttons_layout.addWidget(self.prev_button)
        playback_buttons_layout.addWidget(self.next_button)
        main_layout.addLayout(playback_buttons_layout)

        self.setCentralWidget(central_widget)
        self.resize(700, 350)  # Adjusted width a bit for issue label
        logger.debug("ControlWindow UI setup complete.")
        self._update_issue_display([])  # Initially hide

    # --- NEW: Issue Detection and Display Logic ---
    def _update_playlist_issues(self):
        logger.debug("Updating playlist issues...")
        if not self.playlist or not self.playlist.get_slides():
            self._update_issue_display([])
            return

        issues_found = []
        slides = self.playlist.get_slides()
        num_slides = len(slides)

        for i, slide_data in enumerate(slides):
            slide_issues = {"index": i, "icons": set(), "descriptions": []}  # Use set for unique icons
            duration = slide_data.get("duration", 0)
            loop_target = slide_data.get("loop_to_slide", 0)  # 1-based
            text_overlay = slide_data.get("text_overlay")

            # 1. Timer Useless: Last slide, has duration, no text, no effective loop
            if i == num_slides - 1 and duration > 0 and not text_overlay:
                if loop_target == 0 or loop_target == (i + 1):
                    slide_issues["icons"].add("timer")
                    slide_issues["descriptions"].append("Useless Timer (last slide)")

            # 2. Loop Inactive: Loop target exists, but duration (needed for loop/delay) is 0
            if loop_target > 0 and duration == 0:
                slide_issues["icons"].add("loop")
                slide_issues["descriptions"].append("Inactive Loop (0s duration/delay)")

            # 3. Loop Self: Loops to itself (and not the *only* slide, which is covered by Useless Timer if last)
            if loop_target == (
                    i + 1) and num_slides > 1:  # Avoid flagging single slide looping to self as a primary issue here
                is_last_slide_self_loop = (i == num_slides - 1) and (loop_target == i + 1)
                if not (
                        is_last_slide_self_loop and duration > 0 and not text_overlay):  # Avoid double-flagging with "Useless Timer"
                    slide_issues["icons"].add("loop")
                    slide_issues["descriptions"].append("Self Loop")

            # 4. Text Issues
            if text_overlay:
                para_name = text_overlay.get("paragraph_name")
                start_sent_1based = text_overlay.get("start_sentence")
                end_sent_spec = text_overlay.get("end_sentence")

                if not para_name:
                    slide_issues["icons"].add("text")
                    slide_issues["descriptions"].append("Text Missing (No paragraph name)")
                else:
                    try:
                        para_data = self.paragraph_manager.load_paragraph(para_name)
                        if not para_data:  # Should be caught by FileNotFoundError, but defensive
                            slide_issues["icons"].add("text")
                            slide_issues["descriptions"].append("Text Missing (Not found)")
                        else:
                            num_para_sentences = len(para_data.get("sentences", []))
                            start_idx_0based = start_sent_1based - 1

                            end_idx_0based = -1
                            if isinstance(end_sent_spec, str) and end_sent_spec.lower() == "all":
                                end_idx_0based = num_para_sentences - 1
                            elif isinstance(end_sent_spec, int):
                                end_idx_0based = end_sent_spec - 1

                            if not (0 <= start_idx_0based < num_para_sentences and \
                                    start_idx_0based <= end_idx_0based < num_para_sentences and \
                                    num_para_sentences > 0):
                                slide_issues["icons"].add("text")
                                slide_issues["descriptions"].append("Range Invalid")
                    except (FileNotFoundError, ValueError):
                        slide_issues["icons"].add("text")
                        slide_issues["descriptions"].append("Text Missing (Load error)")

            if slide_issues["icons"]:
                issues_found.append(slide_issues)

        self._update_issue_display(issues_found)

    def _update_issue_display(self, issues_found):
        # Clear previous icons
        while self.issue_icon_layout.count():
            item = self.issue_icon_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if issues_found:
            self.issue_label.setText(f"ISSUES: {len(issues_found)}")

            first_issue_slide_index = issues_found[0]["index"]
            first_issue_icons = sorted(list(issues_found[0]["icons"]))  # Sort for consistent order
            first_issue_descriptions = issues_found[0]["descriptions"]

            # Add icons for the first problematic slide
            for icon_name in first_issue_icons:
                pixmap = self.indicator_icons.get(icon_name)
                if pixmap and not pixmap.isNull():
                    icon_label = QLabel()
                    icon_label.setPixmap(pixmap)
                    self.issue_icon_layout.addWidget(icon_label)

            tooltip_text = f"Slide {first_issue_slide_index + 1} Issues:\n- " + "\n- ".join(first_issue_descriptions)
            if len(issues_found) > 1:
                tooltip_text += f"\n\n({len(issues_found) - 1} other slide(s) also have issues.)"

            self.issue_label.setToolTip(tooltip_text)
            self.issue_icon_widget.setToolTip(tooltip_text)

            self.issue_label.show()
            self.issue_icon_widget.show()
        else:
            self.issue_label.setText("")
            self.issue_label.setToolTip("")
            self.issue_icon_widget.setToolTip("")
            self.issue_label.hide()
            self.issue_icon_widget.hide()

    # --- END NEW ---

    def populate_playlist_view(self):
        # ... (remains the same, but will benefit from issue display) ...
        logger.debug("Populating playlist view...")
        self.playlist_view.clear()

        for i, slide_data in enumerate(self.playlist.get_slides()):
            text_overlay_info = slide_data.get("text_overlay")
            has_text = bool(text_overlay_info and text_overlay_info.get("paragraph_name"))

            composite_icon = create_composite_thumbnail(
                slide_data, i, self.indicator_icons,
                has_text_overlay=has_text
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
                    tooltip_parts.append(f"Loop to Slide {loop_target} (inactive due to 0s duration/delay)")

            if has_text:
                tooltip_parts.append(f"Text: {text_overlay_info.get('paragraph_name', 'N/A')}")

            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_view.addItem(item)
        logger.info(f"Playlist view populated with {self.playlist_view.count()} items.")
        self._update_playlist_issues()  # Update issues after populating

    def _set_slide_index(self, new_index):
        # ... (remains the same) ...
        slides = self.playlist.get_slides()
        num_slides = len(slides)
        old_index = self.current_index
        changed = False

        if not slides:
            if self.current_index != -1:
                self.current_index = -1
                changed = True
                logger.debug(f"Playlist empty, index set to -1 from {old_index}")
        elif 0 <= new_index < num_slides:
            if self.current_index != new_index:
                self.current_index = new_index
                changed = True
                logger.debug(f"Slide index changed from {old_index} to {self.current_index}")
        else:
            if not (0 <= self.current_index < num_slides):
                self.current_index = -1 if slides else -1
                changed = (old_index != self.current_index)
            logger.warning(
                f"Requested index {new_index} is out of bounds (0-{num_slides - 1}). Index remains {self.current_index}.")

        if changed:
            self.update_ui_state()
        return changed

    def _reset_text_state(self):
        # ... (remains the same) ...
        logger.debug("Resetting text state.")
        self.current_paragraph_data = None
        self.current_sentence_index = -1
        self.text_start_index = -1
        self.text_end_index = -1
        self._is_timer_for_initial_text_delay = False
        if self.display_window:
            self.display_window.clearText()

    def _display_current_sentence(self):
        # ... (remains the same) ...
        if not self.current_paragraph_data or self.current_sentence_index < 0:
            logger.debug("_display_current_sentence called but no text active.")
            if self.display_window:
                self.display_window.clearText()
            return

        sentences = self.current_paragraph_data.get("sentences", [])
        if self.text_start_index <= self.current_sentence_index <= self.text_end_index:
            if 0 <= self.current_sentence_index < len(sentences):
                sentence_data = sentences[self.current_sentence_index]
                text = sentence_data.get("text", "")
                logger.info(
                    f"Displaying sentence {self.current_sentence_index - self.text_start_index + 1}/{self.text_end_index - self.text_start_index + 1}: '{text}'")
                if self.display_window:
                    self.display_window.displayText(text)
            else:
                logger.error(
                    f"Sentence index {self.current_sentence_index} is out of bounds for actual sentences list ({len(sentences)}).")
                self._reset_text_state()
        else:
            logger.warning(
                f"Sentence index {self.current_sentence_index} out of range for slide's text overlay ({self.text_start_index}-{self.text_end_index}). Clearing text.")
            self._reset_text_state()

    def _display_current_slide(self):
        # ... (remains the same) ...
        self.slide_timer.stop()
        self._reset_text_state()

        slides = self.playlist.get_slides()
        if not (0 <= self.current_index < len(slides)):
            logger.warning(f"Cannot display: Invalid current_index {self.current_index}. Clearing display.")
            self.clear_display_screen()
            return

        logger.info(f"Displaying slide {self.current_index + 1}.")
        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data:
            logger.critical(f"INCONSISTENCY: No slide_data for valid index {self.current_index}. Clearing.")
            self.clear_display_screen()
            return

        self.is_displaying = True
        self.display_window.display_images(slide_data.get("layers", []))

        text_overlay_info = slide_data.get("text_overlay")
        if text_overlay_info:
            para_name = text_overlay_info.get("paragraph_name")
            start_sent_1based = text_overlay_info.get("start_sentence")
            end_sent = text_overlay_info.get("end_sentence")

            if para_name and start_sent_1based is not None and end_sent is not None:
                try:
                    self.current_paragraph_data = self.paragraph_manager.load_paragraph(para_name)
                    if self.current_paragraph_data:
                        num_para_sentences = len(self.current_paragraph_data.get("sentences", []))
                        self.text_start_index = start_sent_1based - 1

                        if isinstance(end_sent, str) and end_sent.lower() == "all":
                            self.text_end_index = num_para_sentences - 1
                        elif isinstance(end_sent, int):
                            self.text_end_index = end_sent - 1
                        else:
                            logger.error(f"Invalid end_sentence format: {end_sent}. No text shown.")
                            self._reset_text_state()
                            self.update_ui_state()
                            return

                        if 0 <= self.text_start_index < num_para_sentences and \
                                self.text_start_index <= self.text_end_index < num_para_sentences:

                            self.current_sentence_index = self.text_start_index

                            initial_text_delay = slide_data.get("duration", 0)
                            if initial_text_delay > 0:
                                logger.info(
                                    f"Starting initial delay of {initial_text_delay}s for text on slide {self.current_index + 1}.")
                                self._is_timer_for_initial_text_delay = True
                                self.slide_timer.start(initial_text_delay)
                            else:
                                logger.info(
                                    f"No initial delay. Displaying first sentence for slide {self.current_index + 1}.")
                                self._display_current_sentence()
                        else:
                            logger.error(
                                f"Invalid sentence range (0-based: {self.text_start_index}-{self.text_end_index}) for paragraph '{para_name}' ({num_para_sentences} sentences). No text shown.")
                            self._reset_text_state()
                    else:
                        logger.error(f"Failed to load paragraph '{para_name}'. No text shown.")
                        self._reset_text_state()
                except (FileNotFoundError, ValueError) as e:
                    logger.error(f"Error loading paragraph '{para_name}': {e}", exc_info=True)
                    QMessageBox.warning(self, "Text Error", f"Could not load paragraph '{para_name}':\n{e}")
                    self._reset_text_state()
            else:
                logger.warning(f"Slide {self.current_index + 1} has incomplete text_overlay data. No text shown.")
                self._reset_text_state()
        else:
            slide_duration = slide_data.get("duration", 0)
            if slide_duration > 0:
                logger.debug(
                    f"Starting slide duration timer of {slide_duration}s for slide {self.current_index + 1} (no text).")
                self._is_timer_for_initial_text_delay = False
                self.slide_timer.start(slide_duration)

        self.update_ui_state()

    def clear_display_screen(self):
        # ... (remains the same) ...
        self._reset_text_state()

        logger.info("Clearing display screen (images and stopping timer).")
        self.slide_timer.stop()
        if self.display_window:
            self.display_window.clear_display()
        self.is_displaying = False
        self.update_ui_state()

    def update_ui_state(self):
        # ... (remains the same) ...
        self.update_list_selection()
        self.update_show_clear_button_state()
        slides = self.playlist.get_slides()
        has_slides = bool(slides)
        num_slides = len(slides)

        can_go_prev = False
        if has_slides:
            if self.current_sentence_index != -1 and self.current_paragraph_data and \
                    self.current_sentence_index > self.text_start_index:
                can_go_prev = True
            elif self.current_index > 0:
                can_go_prev = True

        can_go_next = False
        if has_slides:
            if self.current_sentence_index != -1 and self.current_paragraph_data and \
                    self.current_sentence_index < self.text_end_index:
                can_go_next = True
            elif self.current_index < num_slides - 1:
                can_go_next = True

        self.prev_button.setEnabled(can_go_prev)
        self.next_button.setEnabled(can_go_next)
        self.show_clear_button.setEnabled(has_slides)

    def update_list_selection(self):
        # ... (remains the same) ...
        logger.debug(f"Updating list selection to index {self.current_index}.")
        item_to_select = None
        if self.playlist_view.count() > 0:
            for i in range(self.playlist_view.count()):
                item = self.playlist_view.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == self.current_index:
                    item_to_select = item
                    break
        try:
            self.playlist_view.currentItemChanged.disconnect(self.handle_list_selection)
        except (TypeError, RuntimeError):
            pass
        self.playlist_view.setCurrentItem(item_to_select)
        if item_to_select:
            self.playlist_view.scrollToItem(item_to_select, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.playlist_view.currentItemChanged.connect(self.handle_list_selection)

    def update_show_clear_button_state(self):
        # ... (remains the same) ...
        if self.is_displaying or (
                self.display_window and self.display_window.text_item and self.display_window.text_item.isVisible()):
            self.show_clear_button.setText(" Clear")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("clear.png")))
            self.show_clear_button.setToolTip("Clear the display (Space or Esc)")
        else:
            self.show_clear_button.setText(" Show")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.show_clear_button.setToolTip("Show the selected slide (Space)")

    def handle_show_clear_click(self):
        # ... (remains the same) ...
        logger.debug("Show/Clear button clicked.")
        if self.is_displaying or (self.display_window and self.display_window.text_item):  # If anything is showing
            self.clear_display_screen()
        else:
            slides = self.playlist.get_slides()
            if not slides:
                QMessageBox.information(self, "No Playlist", "Load a playlist to show a slide.")
                return
            if not (0 <= self.current_index < len(slides)):
                self._set_slide_index(0)
            self._display_current_slide()

    def next_slide(self):
        # ... (remains the same) ...
        logger.debug("Next slide triggered.")

        if self.current_sentence_index != -1 and self.current_paragraph_data:
            if self.current_sentence_index < self.text_end_index:
                self.current_sentence_index += 1
                self._display_current_sentence()
                self.update_ui_state()
                return
            else:
                self._reset_text_state()

        slides = self.playlist.get_slides()
        if not slides or not (self.current_index < len(slides) - 1):
            logger.info("Cannot go next: No slides or already at the end.")
            self.update_ui_state()
            return

        self._set_slide_index(self.current_index + 1)
        self._display_current_slide()

    def prev_slide(self):
        # ... (remains the same) ...
        logger.debug("Previous slide triggered.")

        if self.current_sentence_index != -1 and self.current_paragraph_data:
            if self.current_sentence_index > self.text_start_index:
                self.current_sentence_index -= 1
                self._display_current_sentence()
                self.update_ui_state()
                return
            else:
                self._reset_text_state()

        if not self.playlist.get_slides() or self.current_index <= 0:
            logger.info("Cannot go previous: No slides or already at the start.")
            self.update_ui_state()
            return

        self._set_slide_index(self.current_index - 1)
        self._display_current_slide()

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        # ... (remains the same) ...
        logger.debug("Slide list double-clicked.")
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if self._set_slide_index(index):
                self._display_current_slide()
            elif self.current_index == index:
                self._display_current_slide()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        # ... (remains the same) ...
        logger.debug("List selection changed via UI.")
        self.slide_timer.stop()

        if current_item:
            new_slide_idx = current_item.data(Qt.ItemDataRole.UserRole)
            if self.current_index != new_slide_idx:
                self._set_slide_index(new_slide_idx)
        else:
            self._set_slide_index(-1)
            self.clear_display_screen()

    def auto_advance_or_loop_slide(self):
        # ... (remains the same) ...
        logger.debug(f"SlideTimer timeout. Was for initial text delay: {self._is_timer_for_initial_text_delay}")

        if self._is_timer_for_initial_text_delay:
            self._is_timer_for_initial_text_delay = False
            if self.current_paragraph_data and self.current_sentence_index != -1:
                logger.info("Initial text delay timer expired. Displaying first sentence.")
                self._display_current_sentence()
            else:
                logger.warning("Timer for initial text delay expired, but no text data ready. This is unexpected.")
            return

        if not self.is_displaying:
            logger.warning("Slide duration timer fired but not displaying. Stopping timer.")
            self.slide_timer.stop()
            return

        slide_data = self.playlist.get_slide(self.current_index)
        if not slide_data:
            logger.warning("No current slide data for slide duration timer. Clearing display.")
            self.clear_display_screen()
            return

        if self.current_sentence_index != -1:
            logger.debug("Slide duration timer fired, but text overlay is active. Timer ignored.")
            self.slide_timer.stop()
            return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = slide_data.get("loop_to_slide", 0)

        if loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1
            if 0 <= loop_target_0_based < num_slides:
                logger.info(f"Looping to slide {loop_target_1_based}.")
                self._set_slide_index(loop_target_0_based)
                self._display_current_slide()
                return
            else:
                logger.warning(
                    f"Invalid loop target ({loop_target_1_based}) for slide {self.current_index + 1}. Advancing.")

        if self.current_index < num_slides - 1:
            logger.info("Auto-advancing to next slide (slide duration).")
            self.next_slide()
        else:
            logger.info("Timer expired on last slide (slide duration), no loop. Clearing display.")
            self.clear_display_screen()

    def load_playlist(self, file_path):
        # ... (Method itself remains the same, but its call to _update_playlist_issues is important) ...
        logger.info(f"Attempting to load playlist: {file_path}")
        self.slide_timer.stop()
        self._reset_text_state()
        try:
            self.playlist.load(file_path)
            self.settings_manager.set_current_playlist(file_path)
            logger.info(f"Successfully loaded: {file_path}")
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load playlist {file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist()
            self.settings_manager.set_current_playlist(None)

        self.clear_display_screen()
        self.populate_playlist_view()  # This will call _update_playlist_issues
        self._set_slide_index(0 if self.playlist.get_slides() else -1)
        self.update_ui_state()

    def load_playlist_dialog(self):
        # ... (remains the same) ...
        logger.debug("Opening load playlist dialog...")
        default_dir = get_playlists_path()
        fileName = get_themed_open_filename(self, "Open Playlist", default_dir, "JSON Files (*.json)")
        if fileName:
            self.load_playlist(fileName)

    def load_last_playlist(self):
        # ... (remains the same) ...
        last_playlist = self.settings_manager.get_current_playlist()
        if last_playlist:
            logger.info(f"Loading last used playlist: {last_playlist}")
            self.load_playlist(last_playlist)
        else:
            logger.info("No last playlist found in settings.")
            self.populate_playlist_view()
            self.clear_display_screen()
            self.update_ui_state()

    def open_playlist_editor(self):
        # ... (remains the same) ...
        logger.info("Opening playlist editor...")
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(self.display_window, self.playlist, self)
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        logger.info(f"ControlWindow received signal to reload: {saved_playlist_path}")
        self.load_playlist(saved_playlist_path)  # Reload and re-check issues

    def open_settings_window(self):
        # ... (remains the same) ...
        logger.info("Opening settings window...")
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            self.settings_window_instance = SettingsWindow(self)
            self.settings_window_instance.show()
        else:
            self.settings_window_instance.activateWindow()
            self.settings_window_instance.raise_()

    def toggle_display_window_visibility(self):
        # ... (remains the same) ...
        if self.display_window:
            if self.display_window.isVisible():
                self.display_window.hide()
                self.toggle_display_button.setText("Show Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png")))
            else:
                screens = QApplication.instance().screens()
                display_screen_geometry = None
                if screens:
                    display_target_screen = screens[1] if len(screens) > 1 else screens[0]
                    display_screen_geometry = display_target_screen.geometry()
                    self.display_window.setGeometry(display_screen_geometry)

                self.display_window.showFullScreen()
                self.toggle_display_button.setText("Hide Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("hide_display.png")))

    def close_application(self):
        # ... (remains the same) ...
        logger.info("Close application action initiated...")
        self.close()

    def closeEvent(self, event):
        # ... (remains the same) ...
        logger.debug("ControlWindow closeEvent triggered.")
        self.slide_timer.stop()

        if self.editor_window and self.editor_window.isVisible():
            logger.debug("Attempting to close PlaylistEditorWindow...")
            if not self.editor_window.close():
                logger.warning("PlaylistEditorWindow close cancelled, aborting application quit.")
                event.ignore()
                return

        if self.settings_window_instance and self.settings_window_instance.isVisible():
            logger.debug("Closing SettingsWindow...")
            self.settings_window_instance.close()

        if self.display_window and self.display_window.isVisible():
            logger.debug("Closing DisplayWindow...")
            self.display_window.close()

        logger.info("ControlWindow accepted close. Quitting QApplication.")
        QCoreApplication.instance().quit()
        event.accept()