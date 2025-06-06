# myapp/gui/ui_updater.py
import logging
from PySide6.QtWidgets import QAbstractItemView, QLabel
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from ..utils.paths import get_icon_file_path

logger = logging.getLogger(__name__)


class ControlWindowUIUpdater:
    def __init__(self, control_window):
        self.cw = control_window
        logger.debug("ControlWindowUIUpdater initialized.")

    def update_all(self):
        logger.debug("Updating all UI states.")
        self.update_list_selection()
        self.update_show_clear_button_state()
        self.update_navigation_buttons_state()
        self.update_video_controls_state()

    def update_list_selection(self):
        logger.debug(f"Updating list selection to index {self.cw.current_index}.")
        item_to_select = None
        list_widget = self.cw.playlist_view
        if list_widget.count() > 0:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == self.cw.current_index:
                    item_to_select = item
                    break
        try:
            list_widget.currentItemChanged.disconnect(self.cw.handle_list_selection)
        except (TypeError, RuntimeError):
            pass

        list_widget.setCurrentItem(item_to_select)
        if item_to_select:
            list_widget.scrollToItem(item_to_select, QAbstractItemView.ScrollHint.PositionAtCenter)

        list_widget.currentItemChanged.connect(self.cw.handle_list_selection)

    def update_show_clear_button_state(self):
        button = self.cw.show_clear_button
        is_video_playing = self.cw.display_window and self.cw.display_window.current_video_path
        if self.cw.is_displaying or self.cw.text_controller.is_active() or is_video_playing:
            button.setText(" Clear")
            button.setIcon(QIcon(get_icon_file_path("clear.png")))
            button.setToolTip("Clear the display (Space or Esc)")
        else:
            button.setText(" Show")
            button.setIcon(QIcon(get_icon_file_path("play.png")))
            button.setToolTip("Show the selected slide (Space)")
        button.setEnabled(bool(self.cw.playlist.get_slides()))

    def update_navigation_buttons_state(self):
        slides = self.cw.playlist.get_slides()
        has_slides = bool(slides)
        num_slides = len(slides)

        can_go_prev = False
        if has_slides:
            if self.cw.text_controller.is_active() and not self.cw.text_controller.is_at_start():
                can_go_prev = True
            elif self.cw.current_index > 0:
                can_go_prev = True

        can_go_next = False
        if has_slides:
            if self.cw.text_controller.is_active() and not self.cw.text_controller.is_at_end():
                can_go_next = True
            elif self.cw.current_index < num_slides - 1:
                can_go_next = True

        self.cw.prev_button.setEnabled(can_go_prev)
        self.cw.next_button.setEnabled(can_go_next)

    def update_issue_display(self, issues_found: list):
        label = self.cw.issue_label
        icon_widget = self.cw.issue_icon_widget
        icon_layout = self.cw.issue_icon_layout
        indicator_icons = self.cw.indicator_icons

        while icon_layout.count():
            item = icon_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if issues_found:
            label.setText(f"ISSUES: {len(issues_found)}")
            first_issue_slide_index = issues_found[0]["index"]
            first_issue_icons = sorted(list(issues_found[0]["icons"]))
            first_issue_descriptions = issues_found[0]["descriptions"]

            for icon_name in first_issue_icons:
                pixmap = indicator_icons.get(icon_name)
                if pixmap and not pixmap.isNull():
                    icon_label = QLabel()
                    icon_label.setPixmap(pixmap)
                    icon_layout.addWidget(icon_label)

            tooltip_text = f"Slide {first_issue_slide_index + 1} Issues:\n- " + "\n- ".join(first_issue_descriptions)
            if len(issues_found) > 1:
                tooltip_text += f"\n\n({len(issues_found) - 1} other slide(s) also have issues.)"

            label.setToolTip(tooltip_text)
            icon_widget.setToolTip(tooltip_text)
            label.show()
            icon_widget.show()
        else:
            label.setText("")
            label.setToolTip("")
            icon_widget.setToolTip("")
            label.hide()
            icon_widget.hide()

    def update_video_controls_state(self):
        # --- FIX: Explicitly cast the result to a boolean ---
        is_video_loaded = bool(self.cw.display_window and self.cw.display_window.current_video_path)
        # --- END FIX ---
        self.cw.video_play_pause_button.setEnabled(is_video_loaded)
        self.cw.video_progress_slider.setEnabled(is_video_loaded)
        self.cw.video_time_label.setEnabled(is_video_loaded)
        if not is_video_loaded:
            self.cw.video_time_label.setText("--:-- / --:--")
            self.cw.video_progress_slider.setValue(0)
        self.update_video_button_icon()

    def update_video_time_label(self, position, duration):
        def format_time(ms):
            s = ms // 1000
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h:d}:{m:02d}:{s:02d}"
            return f"{m:02d}:{s:02d}"

        self.cw.video_time_label.setText(f"{format_time(position)} / {format_time(duration)}")

    def update_video_button_icon(self):
        """Updates the video play/pause button icon based on the player's state."""
        state = self.cw.display_window.get_playback_state() if self.cw.display_window else QMediaPlayer.PlaybackState.StoppedState
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.cw.video_play_pause_button.setIcon(QIcon(get_icon_file_path("pause.png")))
            self.cw.video_play_pause_button.setToolTip("Pause Video")
        else:
            self.cw.video_play_pause_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.cw.video_play_pause_button.setToolTip("Play Video")