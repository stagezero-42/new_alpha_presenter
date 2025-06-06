# myapp/media/media_renderer.py
import os
import logging
import html
from PySide6.QtWidgets import (
    QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsTextItem
)
from PySide6.QtGui import (
    QPixmap, QPainter, QBrush, QColor, QIcon,
    QFont, QTextOption, QTextCursor, QTextCharFormat
)
from PySide6.QtCore import Qt, QRectF, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

from ..utils.paths import get_media_file_path, get_icon_file_path
from ..utils.schemas import (
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_FONT_COLOR,
    DEFAULT_BACKGROUND_COLOR, DEFAULT_BACKGROUND_ALPHA,
    DEFAULT_TEXT_ALIGN, DEFAULT_TEXT_VERTICAL_ALIGN, DEFAULT_FIT_TO_WIDTH
)

logger = logging.getLogger(__name__)

TEXT_MARGIN_HORIZONTAL = 30
TEXT_MARGIN_VERTICAL_TOP_BOTTOM = 50
TEXT_PADDING_CSS = "15px"
TEXT_BORDER_RADIUS_CSS = "10px"


class MediaRenderer(QMainWindow):
    video_duration_changed = Signal(int)
    video_position_changed = Signal(int)
    video_state_changed = Signal(QMediaPlayer.PlaybackState)

    def __init__(self):
        super().__init__()
        logger.debug("Initializing MediaRenderer...")
        self.setWindowTitle("Display Window")

        try:
            icon_name = "app_icon.png"
            icon_path = get_icon_file_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Failed to set MediaRenderer window icon: {e}", exc_info=True)

        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.view.setBackgroundBrush(QBrush(QColor(0, 0, 0)))
        self.view.setStyleSheet("border: 0px")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setCentralWidget(self.view)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.video_item = QGraphicsVideoItem()
        self.media_player.setVideoOutput(self.video_item)
        self.scene.addItem(self.video_item)

        self._play_request_pending = False
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.durationChanged.connect(self._handle_duration_changed)
        self.media_player.positionChanged.connect(self._handle_position_changed)
        self.media_player.playbackStateChanged.connect(self._handle_state_changed)

        self.current_layers = []
        self.current_video_path = None
        self.text_item = None
        self.current_text = None
        self.current_style_options = {}
        logger.debug("MediaRenderer initialized.")

    def set_volume(self, volume: float):
        if 0.0 <= volume <= 1.0:
            self.audio_output.setVolume(volume)
            logger.debug(f"MediaRenderer volume set to {volume}")

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        logger.debug(f"Media status changed: {status}")
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._play_request_pending:
            logger.info("Media is loaded and a play request is pending. Starting playback.")
            self.media_player.play()
            self._play_request_pending = False

    def _handle_duration_changed(self, duration: int):
        self.video_duration_changed.emit(duration)

    def _handle_position_changed(self, position: int):
        self.video_position_changed.emit(position)

    def _handle_state_changed(self, state: QMediaPlayer.PlaybackState):
        self.video_state_changed.emit(state)

    def display_slide(self, slide_data):
        self.clear_display()

        video_path = slide_data.get("video_path")
        if video_path:
            self.display_video(video_path)
            self.set_volume(slide_data.get("video_volume", 0.8))
        else:
            self.display_images(slide_data.get("layers", []))

        text_overlay_settings = slide_data.get("text_overlay")
        if text_overlay_settings and text_overlay_settings.get("paragraph_name"):
            self.current_text = ""
            self.current_style_options = text_overlay_settings
        else:
            self.current_text = None
            self.current_style_options = {}

    def display_video(self, video_filename):
        logger.debug(f"Displaying video: {video_filename}")
        self._play_request_pending = False
        self.current_video_path = get_media_file_path(video_filename)
        if not os.path.exists(self.current_video_path):
            logger.error(f"Video file not found: {self.current_video_path}")
            return

        self.video_item.setVisible(True)
        self.media_player.setSource(QUrl.fromLocalFile(self.current_video_path))
        self.resizeEvent(None)

    def play_video(self):
        if not self.current_video_path:
            return

        logger.info("Play requested. Checking media status...")
        if self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.LoadedMedia:
            logger.debug("Media already loaded, playing immediately.")
            self.media_player.play()
        else:
            logger.debug("Media not loaded yet. Setting pending play request.")
            self._play_request_pending = True

    def pause_video(self):
        if self.current_video_path:
            self._play_request_pending = False
            self.media_player.pause()

    def stop_video(self):
        if self.current_video_path:
            self._play_request_pending = False
            self.media_player.stop()

    def seek_video(self, position):
        if self.current_video_path:
            self.media_player.setPosition(position)

    def get_playback_state(self):
        return self.media_player.playbackState()

    def display_images(self, image_filenames):
        self.video_item.setVisible(False)
        self.media_player.setSource(QUrl())
        self.current_video_path = None
        logger.debug(f"Displaying images: {image_filenames}")

        for item in self.scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                self.scene.removeItem(item)
        self.current_layers = image_filenames

        if not image_filenames:
            logger.info("No images to display for the current slide.")
            return

        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty(): view_rect = self.rect()
        if view_rect.isEmpty():
            logger.warning("View or window rect is empty, cannot scale images.")
            return

        for i, filename in enumerate(image_filenames):
            full_path = get_media_file_path(filename)
            if not os.path.exists(full_path):
                logger.warning(f"Image not found: {full_path}");
                continue
            pixmap = QPixmap(full_path)
            if pixmap.isNull():
                logger.warning(f"Failed to load image: {full_path}");
                continue

            pixmap_scaled = pixmap.scaled(view_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            item = QGraphicsPixmapItem(pixmap_scaled)
            item.setPos((view_rect.width() - pixmap_scaled.width()) / 2,
                        (view_rect.height() - pixmap_scaled.height()) / 2)
            item.setZValue(i)
            self.scene.addItem(item)
        self.scene.setSceneRect(QRectF(view_rect))
        logger.debug("Image display complete.")

    def grab_screenshot(self):
        return self.view.grab()

    def displayText(self, text_to_display: str, style_options: dict = None):
        self.clearText()
        self.current_text = text_to_display
        self.current_style_options = style_options if isinstance(style_options, dict) else {}
        if not text_to_display:
            logger.debug("displayText called with empty text, clearing.")
            return

        logger.debug(f"Displaying text: '{text_to_display[:50]}...' with options: {self.current_style_options}")
        font_family = self.current_style_options.get("font_family", DEFAULT_FONT_FAMILY)
        font_size = self.current_style_options.get("font_size", DEFAULT_FONT_SIZE)
        font_color_hex = self.current_style_options.get("font_color", DEFAULT_FONT_COLOR)
        bg_color_hex = self.current_style_options.get("background_color", DEFAULT_BACKGROUND_COLOR)
        bg_alpha_int = self.current_style_options.get("background_alpha", DEFAULT_BACKGROUND_ALPHA)
        h_align = self.current_style_options.get("text_align", DEFAULT_TEXT_ALIGN)
        v_align = self.current_style_options.get("text_vertical_align", DEFAULT_TEXT_VERTICAL_ALIGN)
        fit_to_width = self.current_style_options.get("fit_to_width", DEFAULT_FIT_TO_WIDTH)
        font = QFont(font_family, font_size)
        font.setBold(True)
        q_bg_color = QColor(bg_color_hex)
        q_bg_color.setAlpha(bg_alpha_int)
        bg_color_rgba_css = f"rgba({q_bg_color.red()}, {q_bg_color.green()}, {q_bg_color.blue()}, {q_bg_color.alphaF():.3f})"
        escaped_text_with_br = html.escape(text_to_display).replace("\n", "<br/>")
        self.text_item = QGraphicsTextItem()
        self.text_item.setFont(font)
        text_document = self.text_item.document()
        root_frame_format = text_document.rootFrame().frameFormat()
        root_frame_format.setBackground(QBrush(Qt.GlobalColor.transparent))
        text_document.rootFrame().setFrameFormat(root_frame_format)
        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty(): view_rect = self.rect()
        if view_rect.isEmpty():
            logger.warning("View or window rect is empty, cannot display text properly.")
            return
        width_style_css = ""
        text_item_layout_width = -1
        if fit_to_width:
            calculated_width = view_rect.width() - 2 * TEXT_MARGIN_HORIZONTAL
            text_item_layout_width = calculated_width
            width_style_css = f"width: {calculated_width}px; box-sizing: border-box;"
        html_content = (
            f"<div style='"
            f"background-color: {bg_color_rgba_css}; "
            f"color: {font_color_hex}; "
            f"padding: {TEXT_PADDING_CSS}; "
            f"border-radius: {TEXT_BORDER_RADIUS_CSS}; "
            f"{width_style_css}'"
            f">{escaped_text_with_br}</div>"
        )
        self.text_item.setHtml(html_content)
        first_block = text_document.firstBlock()
        if first_block.isValid():
            cursor = QTextCursor(first_block)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            char_format_for_bg_clear = QTextCharFormat()
            char_format_for_bg_clear.setBackground(QBrush(Qt.GlobalColor.transparent))
            cursor.mergeCharFormat(char_format_for_bg_clear)
        doc_option = text_document.defaultTextOption()
        if not fit_to_width:
            text_item_layout_width = text_document.idealWidth()
        self.text_item.setTextWidth(text_item_layout_width)
        if h_align == "left":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignLeft)
        elif h_align == "center":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        elif h_align == "right":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignRight)
        text_document.setDefaultTextOption(doc_option)
        text_bounding_rect = self.text_item.boundingRect()
        pos_x = 0
        if fit_to_width:
            pos_x = TEXT_MARGIN_HORIZONTAL
        else:
            pos_x = (view_rect.width() - text_bounding_rect.width()) / 2
        pos_y = 0
        if v_align == "top":
            pos_y = TEXT_MARGIN_VERTICAL_TOP_BOTTOM
        elif v_align == "middle":
            pos_y = (view_rect.height() - text_bounding_rect.height()) / 2
        elif v_align == "bottom":
            pos_y = view_rect.height() - text_bounding_rect.height() - TEXT_MARGIN_VERTICAL_TOP_BOTTOM
        self.text_item.setPos(pos_x, pos_y)
        self.text_item.setZValue(1000)
        self.scene.addItem(self.text_item)
        logger.debug(
            f"Text item added. Pos: ({pos_x:.1f}, {pos_y:.1f}), Size: ({text_bounding_rect.width():.1f}, {text_bounding_rect.height():.1f})")

    def clearText(self):
        if self.text_item and self.text_item in self.scene.items():
            logger.debug("Clearing text item.")
            self.scene.removeItem(self.text_item)
            self.text_item = None

    def clear_display(self):
        logger.info("Clearing display (images, video, and text).")
        self.clearText()
        self.current_text = None
        self.current_style_options = {}
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.video_item.setVisible(False)
        self.current_video_path = None

        for item in self.scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                self.scene.removeItem(item)
        self.current_layers = []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        logger.debug("Resize event, re-rendering content.")
        if self.current_video_path:
            self.video_item.setSize(self.view.viewport().size())
            self.scene.setSceneRect(QRectF(self.view.viewport().rect()))
        else:
            self.display_images(self.current_layers)

    def showEvent(self, event):
        super().showEvent(event)
        logger.debug("Show event, re-rendering content if needed.")
        if self.current_video_path:
            self.video_item.setSize(self.view.viewport().size())
            self.scene.setSceneRect(QRectF(self.view.viewport().rect()))
        else:
            self.display_images(self.current_layers)