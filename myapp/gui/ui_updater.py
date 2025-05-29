# myapp/gui/ui_updater.py
import logging
from PySide6.QtWidgets import QAbstractItemView, QLabel
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from ..utils.paths import get_icon_file_path

# Forward declaration to avoid circular import issues with type hinting
# In a real scenario, you might use interfaces or restructure.
# For now, we'll rely on duck typing or 'Any' if needed.
# from .control_window import ControlWindow

logger = logging.getLogger(__name__)

class ControlWindowUIUpdater:
    """
    Manages updating the UI elements of the ControlWindow based on state changes.
    """

    def __init__(self, control_window):
        """
        Initializes the UI Updater.

        Args:
            control_window: The main ControlWindow instance.
        """
        self.cw = control_window
        logger.debug("ControlWindowUIUpdater initialized.")

    def update_all(self):
        """Updates all relevant UI elements."""
        logger.debug("Updating all UI states.")
        self.update_list_selection()
        self.update_show_clear_button_state()
        self.update_navigation_buttons_state()
        # Note: Issue display is updated separately when the playlist changes.

    def update_list_selection(self):
        """Updates the selection in the QListWidget to match the current index."""
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
            # Temporarily disconnect to prevent feedback loops during update
            list_widget.currentItemChanged.disconnect(self.cw.handle_list_selection)
        except (TypeError, RuntimeError):
            pass  # Not connected or already disconnected

        list_widget.setCurrentItem(item_to_select)
        if item_to_select:
            list_widget.scrollToItem(item_to_select, QAbstractItemView.ScrollHint.PositionAtCenter)

        # Reconnect the signal handler
        list_widget.currentItemChanged.connect(self.cw.handle_list_selection)

    def update_show_clear_button_state(self):
        """Updates the text, icon, and tooltip of the Show/Clear button."""
        button = self.cw.show_clear_button
        if self.cw.is_displaying or self.cw.text_controller.is_active():
            button.setText(" Clear")
            button.setIcon(QIcon(get_icon_file_path("clear.png")))
            button.setToolTip("Clear the display (Space or Esc)")
        else:
            button.setText(" Show")
            button.setIcon(QIcon(get_icon_file_path("play.png")))
            button.setToolTip("Show the selected slide (Space)")

        button.setEnabled(bool(self.cw.playlist.get_slides()))


    def update_navigation_buttons_state(self):
        """Updates the enabled state of the Prev/Next buttons."""
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
        """Updates the UI elements to show detected playlist issues."""
        label = self.cw.issue_label
        icon_widget = self.cw.issue_icon_widget
        icon_layout = self.cw.issue_icon_layout
        indicator_icons = self.cw.indicator_icons

        # Clear previous icons
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