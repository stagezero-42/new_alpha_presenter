# myapp/gui/control_window.py
import os
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QFileDialog, QListWidget, QListWidgetItem, QHBoxLayout, QApplication,
    QListView, QAbstractItemView
)
from PySide6.QtCore import QCoreApplication, QSize, Qt, QTimer, QPoint
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor  # Added QColor

from .playlist_editor import PlaylistEditorWindow
from ..playlist.playlist import Playlist
from ..utils.paths import get_icon_file_path, get_media_path, get_playlists_path
from ..settings.settings_manager import SettingsManager
from myapp.settings.key_bindings import setup_keybindings
from myapp import __version__

# Define sizes for the composite thumbnail
THUMBNAIL_IMAGE_WIDTH = 120  # Width of the actual image part
THUMBNAIL_IMAGE_HEIGHT = 90  # Height of the actual image part
INDICATOR_AREA_HEIGHT = 25  # Height of the area below for icons & text
INDICATOR_ICON_SIZE = 16  # Size of small status icons (timer, loop)
TOTAL_ICON_WIDTH = THUMBNAIL_IMAGE_WIDTH
TOTAL_ICON_HEIGHT = THUMBNAIL_IMAGE_HEIGHT + INDICATOR_AREA_HEIGHT

# Height for the QListWidget itself
LIST_WIDGET_HEIGHT = TOTAL_ICON_HEIGHT + 25  # Total icon height + item padding


class ControlWindow(QMainWindow):
    def __init__(self, display_window):
        super().__init__()
        self.setWindowTitle(f"Control Window v{__version__}")
        self.display_window = display_window
        if not display_window: raise ValueError("DisplayWindow instance must be provided.")

        self.settings_manager = SettingsManager()
        self.playlist = Playlist()
        self.current_index = -1
        self.is_displaying = False
        self.editor_window = None

        self.slide_timer = QTimer(self)
        self.slide_timer.setSingleShot(True)
        self.slide_timer.timeout.connect(self.auto_advance_or_loop_slide)

        # Pre-load indicator icons as QPixmaps
        try:
            self.pix_slide_indicator = QPixmap(get_icon_file_path("slide_icon.png")).scaled(
                INDICATOR_ICON_SIZE, INDICATOR_ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.pix_timer_indicator = QPixmap(get_icon_file_path("timer_icon.png")).scaled(
                INDICATOR_ICON_SIZE, INDICATOR_ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.pix_loop_indicator = QPixmap(get_icon_file_path("loop_icon.png")).scaled(
                INDICATOR_ICON_SIZE, INDICATOR_ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        except Exception as e:
            print(f"Warning: Could not load all indicator icons: {e}")
            self.pix_slide_indicator = QPixmap()  # Empty pixmap as fallback
            self.pix_timer_indicator = QPixmap()
            self.pix_loop_indicator = QPixmap()

        self.setup_ui()
        setup_keybindings(self, self.settings_manager)
        self.update_show_clear_button_state()
        self.clear_display_screen()
        self.load_last_playlist()

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        playlist_buttons_layout = QHBoxLayout()
        self.load_button = QPushButton(" Load")
        self.edit_button = QPushButton(" Edit")
        self.toggle_display_button = QPushButton("Show Display")
        self.close_button = QPushButton(" Close")

        self.load_button.setIcon(QIcon(get_icon_file_path("load.png")))
        self.load_button.setToolTip("Load a playlist (Ctrl+L)")
        self.edit_button.setIcon(QIcon(get_icon_file_path("edit.png")))
        self.edit_button.setToolTip("Open the Playlist Editor (Ctrl+E)")
        self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png")))
        self.toggle_display_button.setToolTip("Show or Hide the Display Window")
        self.close_button.setIcon(QIcon(get_icon_file_path("close.png")))
        self.close_button.setToolTip("Close the application (Ctrl+Q)")

        self.load_button.clicked.connect(self.load_playlist_dialog)
        self.edit_button.clicked.connect(self.open_playlist_editor)
        self.toggle_display_button.clicked.connect(self.toggle_display_window_visibility)
        self.close_button.clicked.connect(self.close_application)

        playlist_buttons_layout.addWidget(self.load_button)
        playlist_buttons_layout.addWidget(self.edit_button)
        playlist_buttons_layout.addWidget(self.toggle_display_button)
        playlist_buttons_layout.addWidget(self.close_button)
        main_layout.addLayout(playlist_buttons_layout)

        self.playlist_view = QListWidget()
        self.playlist_view.setViewMode(QListView.ViewMode.IconMode)
        self.playlist_view.setFlow(QListView.Flow.LeftToRight)
        self.playlist_view.setMovement(QListView.Movement.Static)
        self.playlist_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.playlist_view.setWrapping(False)

        self.playlist_view.setIconSize(QSize(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT))  # Use total size

        self.playlist_view.setSpacing(5)  # Reduced spacing a bit
        self.playlist_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlist_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.playlist_view.setFixedHeight(LIST_WIDGET_HEIGHT)  # Use calculated height

        self.playlist_view.currentItemChanged.connect(self.handle_list_selection)
        self.playlist_view.itemDoubleClicked.connect(self.go_to_selected_slide_from_list)
        main_layout.addWidget(self.playlist_view)

        playback_buttons_layout = QHBoxLayout()
        self.show_clear_button = QPushButton()
        self.show_clear_button.clicked.connect(self.handle_show_clear_click)

        self.prev_button = QPushButton(" Prev")
        self.prev_button.setIcon(QIcon(get_icon_file_path("previous.png")))
        self.prev_button.setToolTip("Previous slide (Arrow Keys, Page Up/Down)")
        self.prev_button.clicked.connect(self.prev_slide)

        self.next_button = QPushButton(" Next")
        self.next_button.setIcon(QIcon(get_icon_file_path("next.png")))
        self.next_button.setToolTip("Next slide (Arrow Keys, Page Up/Down)")
        self.next_button.clicked.connect(self.next_slide)

        playback_buttons_layout.addWidget(self.show_clear_button)
        playback_buttons_layout.addWidget(self.prev_button)
        playback_buttons_layout.addWidget(self.next_button)
        main_layout.addLayout(playback_buttons_layout)

        self.setCentralWidget(central_widget)
        self.resize(600, 350)

    def create_composite_thumbnail(self, slide_data, slide_index):
        media_base_path = get_media_path()

        canvas_pixmap = QPixmap(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)
        canvas_pixmap.fill(Qt.GlobalColor.transparent)  # Start with transparent

        painter = QPainter(canvas_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 1. Draw the main image thumbnail
        image_part_pixmap = QPixmap(THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT)
        image_part_pixmap.fill(Qt.GlobalColor.darkGray)  # Background for the image part

        layers = slide_data.get("layers", [])
        if layers:
            first_image_filename = layers[0]
            image_path = os.path.join(media_base_path, first_image_filename)
            if os.path.exists(image_path):
                original_pixmap = QPixmap(image_path)
                if not original_pixmap.isNull():
                    scaled_pixmap = original_pixmap.scaled(
                        THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    # Center the scaled image onto image_part_pixmap
                    x_img = (THUMBNAIL_IMAGE_WIDTH - scaled_pixmap.width()) / 2
                    y_img = (THUMBNAIL_IMAGE_HEIGHT - scaled_pixmap.height()) / 2

                    temp_painter = QPainter(image_part_pixmap)  # Paint on the image_part_pixmap
                    temp_painter.drawPixmap(QPoint(int(x_img), int(y_img)), scaled_pixmap)
                    temp_painter.end()

        painter.drawPixmap(0, 0, image_part_pixmap)

        # 2. Draw indicator area below the image thumbnail
        indicator_y_start = THUMBNAIL_IMAGE_HEIGHT + 2  # Small gap
        current_x = 5  # Starting X for indicators & text

        # Set font for text (slide number)
        font = painter.font()
        font.setPointSize(9)  # Adjust as needed
        painter.setFont(font)
        painter.setPen(QColor(Qt.GlobalColor.black))  # Text color

        # Draw Slide Icon + Number
        if not self.pix_slide_indicator.isNull():
            painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2,
                               self.pix_slide_indicator)
        current_x += INDICATOR_ICON_SIZE + 2

        slide_num_text = str(slide_index + 1)
        text_rect = painter.fontMetrics().boundingRect(slide_num_text)
        painter.drawText(current_x, indicator_y_start + (
                    INDICATOR_AREA_HEIGHT - text_rect.height()) // 2 + text_rect.height() - painter.fontMetrics().descent(),
                         slide_num_text)
        current_x += text_rect.width() + 7  # Add more spacing after number

        duration = slide_data.get("duration", 0)
        loop_target = slide_data.get("loop_to_slide", 0)

        if duration > 0:
            if not self.pix_timer_indicator.isNull():
                painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2,
                                   self.pix_timer_indicator)
            current_x += INDICATOR_ICON_SIZE + 7

        if loop_target > 0 and duration > 0:
            if not self.pix_loop_indicator.isNull():
                painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2,
                                   self.pix_loop_indicator)
            # current_x += INDICATOR_ICON_SIZE + 2 # No text after loop icon

        painter.end()
        return QIcon(canvas_pixmap)

    def populate_playlist_view(self):
        self.playlist_view.clear()
        for i, slide_data in enumerate(self.playlist.get_slides()):

            composite_icon = self.create_composite_thumbnail(slide_data, i)
            item = QListWidgetItem(composite_icon, "")  # Set composite icon, item text is empty

            tooltip_parts = [f"Slide {i + 1}"]
            duration = slide_data.get("duration", 0)
            loop_target = slide_data.get("loop_to_slide", 0)

            if duration > 0:
                tooltip_parts.append(f"Plays for: {duration}s")
            else:
                tooltip_parts.append("Manual advance")

            if loop_target > 0:
                if duration > 0:
                    tooltip_parts.append(f"Loops to: Slide {loop_target}")
                else:
                    tooltip_parts.append(f"Loop to Slide {loop_target} (inactive due to 0s duration)")

            item.setToolTip("\n".join(tooltip_parts))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_view.addItem(item)

        self.update_list_selection()

    # ... (rest of the methods: auto_advance_or_loop_slide, update_show_clear_button_state, etc., remain the same as your last working version)
    def auto_advance_or_loop_slide(self):
        print("Timer triggered.")
        if not self.is_displaying:
            print("Display not active, timer ignored.")
            return

        current_slide_data = self.playlist.get_slide(self.current_index)
        if not current_slide_data:
            print("No current slide data, timer ignored.")
            return

        num_slides = len(self.playlist.get_slides())
        loop_target_1_based = current_slide_data.get("loop_to_slide", 0)
        duration = current_slide_data.get("duration", 0)

        if duration > 0 and loop_target_1_based > 0:
            loop_target_0_based = loop_target_1_based - 1

            if loop_target_0_based == self.current_index:
                print(f"Slide {self.current_index + 1} loops to itself. Ignoring loop, proceeding to next if not last.")
            elif 0 <= loop_target_0_based < num_slides:
                print(f"Looping from slide {self.current_index + 1} to slide {loop_target_1_based}.")
                self.current_index = loop_target_0_based
                self.update_display()
                return
            else:
                print(
                    f"Invalid loop target ({loop_target_1_based}) from slide {self.current_index + 1}. Ignoring loop.")

        if self.current_index < (num_slides - 1):
            print("Auto-advancing to next slide.")
            self.next_slide()
        else:
            print("Timer expired on the last slide or no valid action, stopping.")

    def update_show_clear_button_state(self):
        if self.is_displaying:
            self.show_clear_button.setText(" Clear")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("clear.png")))
            self.show_clear_button.setToolTip("Clear the display (Space or Esc)")
        else:
            self.show_clear_button.setText(" Show")
            self.show_clear_button.setIcon(QIcon(get_icon_file_path("play.png")))
            self.show_clear_button.setToolTip("Show the selected slide (Space)")

    def handle_show_clear_click(self):
        if self.slide_timer.isActive():
            self.slide_timer.stop()
            print("Timer stopped by manual Show/Clear click.")
        if self.is_displaying:
            self.clear_display_screen()
        else:
            self.start_or_go_slide()

    def toggle_display_window_visibility(self):
        if self.display_window:
            if self.display_window.isVisible():
                self.display_window.hide()
                self.toggle_display_button.setText("Show Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("show_display.png")))
            else:
                self.display_window.showFullScreen()
                self.toggle_display_button.setText("Hide Display")
                self.toggle_display_button.setIcon(QIcon(get_icon_file_path("hide_display.png")))

    def open_playlist_editor(self):
        if self.editor_window is None or not self.editor_window.isVisible():
            self.editor_window = PlaylistEditorWindow(
                display_window_instance=self.display_window,
                playlist_obj=self.playlist,
                parent=self
            )
            self.editor_window.playlist_saved_signal.connect(self.handle_playlist_saved_by_editor)
            self.editor_window.show()
        else:
            self.editor_window.activateWindow()
            self.editor_window.raise_()

    def handle_playlist_saved_by_editor(self, saved_playlist_path):
        print(f"ControlWindow received signal to reload: {saved_playlist_path}")
        self.load_playlist(saved_playlist_path)

    def load_playlist_dialog(self):
        default_dir = get_playlists_path()
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Playlist", default_dir, "JSON Files (*.json)")
        if fileName:
            self.load_playlist(fileName)
            return True
        return False

    def load_playlist(self, file_path):
        try:
            self.playlist.load(file_path)
            self.current_index = 0 if self.playlist.get_slides() else -1
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.settings_manager.set_current_playlist(file_path)
            print(f"Loaded: {file_path}")
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            self.playlist = Playlist()
            self.current_index = -1
            self.is_displaying = False
            self.populate_playlist_view()
            self.clear_display_screen()
            self.settings_manager.set_current_playlist(None)

    def load_last_playlist(self):
        last_playlist = self.settings_manager.get_current_playlist()
        if last_playlist:
            print(f"Loading last used playlist: {last_playlist}")
            self.load_playlist(last_playlist)
        else:
            print("No last playlist found in settings.")
            self.clear_display_screen()

    def start_or_go_slide(self):
        if self.slide_timer.isActive():
            self.slide_timer.stop()
            print("Timer stopped by manual Start/Go.")
        slides = self.playlist.get_slides()
        if not slides:
            QMessageBox.information(self, "No Playlist", "Load a playlist to show a slide.")
            return
        current_item = self.playlist_view.currentItem()
        if current_item:
            self.current_index = current_item.data(Qt.ItemDataRole.UserRole)
        elif not (0 <= self.current_index < len(slides)):
            self.current_index = 0

        self.update_display()

    def go_to_selected_slide_from_list(self, item: QListWidgetItem):
        if self.slide_timer.isActive():
            self.slide_timer.stop()
            print("Timer stopped by slide list double-click.")
        if item:
            self.current_index = item.data(Qt.ItemDataRole.UserRole)
            self.update_display()

    def handle_list_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        if current_item:
            new_index = current_item.data(Qt.ItemDataRole.UserRole)
            if self.slide_timer.isActive() and new_index != self.current_index:
                self.slide_timer.stop()
                print("Timer stopped due to new slide selection in list.")
            self.current_index = new_index

    def update_display(self):
        if self.slide_timer.isActive():
            self.slide_timer.stop()
            print("Timer stopped before displaying new slide.")

        if self.display_window and not self.display_window.isVisible():
            self.toggle_display_window_visibility()

        slide_data = self.playlist.get_slide(self.current_index)

        if slide_data:
            self.is_displaying = True
            image_filenames = slide_data.get("layers", [])
            self.display_window.display_images(image_filenames, get_media_path())
            self.update_list_selection()

            duration = slide_data.get("duration", 0)
            loop_target_1_based = slide_data.get("loop_to_slide", 0)
            num_slides = len(self.playlist.get_slides())

            if duration > 0:
                print(
                    f"Starting timer for slide {self.current_index + 1} ({duration}s). Loop target: {loop_target_1_based if loop_target_1_based > 0 else 'None'}")
                self.slide_timer.start(duration * 1000)
            else:
                print(f"Slide {self.current_index + 1} has 0s duration. Manual advance.")
                if loop_target_1_based > 0:
                    print(f"  (Loop target {loop_target_1_based} ignored due to 0s duration)")
        else:
            self.is_displaying = False
            if self.display_window: self.display_window.clear_display()

        self.update_show_clear_button_state()

    def update_list_selection(self):
        if 0 <= self.current_index < self.playlist_view.count():
            for i in range(self.playlist_view.count()):
                item = self.playlist_view.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == self.current_index:
                    self.playlist_view.setCurrentItem(item)
                    self.playlist_view.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                    break

    def next_slide(self):
        if self.slide_timer.isActive():
            self.slide_timer.stop()
            print("Timer stopped by Next button.")
        slides = self.playlist.get_slides()
        if not slides: return
        if self.current_index < len(slides) - 1:
            self.current_index += 1
            self.update_display()
        elif self.is_displaying:
            print("End of playlist reached (from Next button).")

    def prev_slide(self):
        if self.slide_timer.isActive():
            self.slide_timer.stop()
            print("Timer stopped by Previous button.")
        slides = self.playlist.get_slides()
        if not slides: return
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()
        elif self.is_displaying:
            print("Beginning of playlist reached (from Prev button).")

    def clear_display_screen(self):
        if self.slide_timer.isActive():
            self.slide_timer.stop()
            print("Timer stopped by Clear Display.")
        if self.display_window:
            self.display_window.clear_display()
        self.is_displaying = False
        self.update_show_clear_button_state()
        print("Display cleared by ControlWindow.")

    def close_application(self):
        print("Attempting to close application...")
        if self.slide_timer.isActive(): self.slide_timer.stop()
        if self.editor_window and self.editor_window.isVisible():
            if not self.editor_window.close():
                print("Editor close cancelled, aborting application close.")
                return
        if self.display_window:
            print("Closing display window...")
            self.display_window.close()
        print("Closing control window...")
        self.close()
        print("Quitting QApplication instance.")
        QCoreApplication.instance().quit()

    def closeEvent(self, event):
        print("ControlWindow closeEvent triggered.")
        if self.slide_timer.isActive(): self.slide_timer.stop()
        if self.display_window and self.display_window.isVisible():
            self.display_window.close()
        if self.editor_window and self.editor_window.isVisible():
            self.editor_window.close()
        super().closeEvent(event)
        print("ControlWindow closeEvent finished.")