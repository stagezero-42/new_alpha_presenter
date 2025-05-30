# myapp/media/media_renderer.py
import os
import logging
import html  # For html.escape
from PySide6.QtWidgets import (
    QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsTextItem
)
from PySide6.QtGui import (
    QPixmap, QPainter, QBrush, QColor, QIcon,
    QFont, QTextOption, QTextCursor, QTextCharFormat  # QPalette removed, QTextCursor & QTextCharFormat kept
)
from PySide6.QtCore import Qt, QRectF
from ..utils.paths import get_media_file_path, get_icon_file_path
from ..utils.schemas import (  # Import defaults for styling
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_FONT_COLOR,
    DEFAULT_BACKGROUND_COLOR, DEFAULT_BACKGROUND_ALPHA,
    DEFAULT_TEXT_ALIGN, DEFAULT_TEXT_VERTICAL_ALIGN, DEFAULT_FIT_TO_WIDTH
)

logger = logging.getLogger(__name__)

# Define some margins for text display
TEXT_MARGIN_HORIZONTAL = 30
TEXT_MARGIN_VERTICAL_TOP_BOTTOM = 50
TEXT_PADDING_CSS = "15px"
TEXT_BORDER_RADIUS_CSS = "10px"


class MediaRenderer(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.debug("Initializing MediaRenderer...")  #
        self.setWindowTitle("Display Window")  #

        try:
            icon_name = "app_icon.png"  #
            icon_path = get_icon_file_path(icon_name)  #
            if icon_path and os.path.exists(icon_path):  #
                self.setWindowIcon(QIcon(icon_path))  #
        except Exception as e:
            logger.error(f"Failed to set MediaRenderer window icon: {e}", exc_info=True)  #

        self.view = QGraphicsView()  #
        self.scene = QGraphicsScene()  #
        self.view.setScene(self.scene)  #
        self.view.setBackgroundBrush(QBrush(QColor(0, 0, 0)))  #
        self.view.setStyleSheet("border: 0px")  #
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)  #
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)  #
        self.setCentralWidget(self.view)  #
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)  #

        self.current_layers = []  #
        self.text_item = None  #
        self.current_text = None  #
        self.current_style_options = {}  #
        logger.debug("MediaRenderer initialized.")  #

    def display_images(self, image_filenames):
        logger.debug(f"Displaying images: {image_filenames}")  #

        temp_text_item = self.text_item  #
        if temp_text_item and temp_text_item in self.scene.items():  #
            self.scene.removeItem(temp_text_item)  #

        for item in self.scene.items():  #
            if isinstance(item, QGraphicsPixmapItem):  #
                self.scene.removeItem(item)  #

        self.current_layers = image_filenames  #

        if not image_filenames:  #
            logger.info("No images to display for the current slide.")  #
            if self.current_text:  #
                self.displayText(self.current_text, self.current_style_options)  #
            return  #

        view_rect = self.view.viewport().rect()  #
        if view_rect.isEmpty(): view_rect = self.rect()  #
        if view_rect.isEmpty():  #
            logger.warning("View or window rect is empty, cannot scale images.")  #
            if self.current_text:  #
                self.displayText(self.current_text, self.current_style_options)  #
            return  #

        for i, filename in enumerate(image_filenames):  #
            full_path = get_media_file_path(filename)  #
            if not os.path.exists(full_path):  #
                logger.warning(f"Image not found: {full_path}");  #
                continue  #
            pixmap = QPixmap(full_path)  #
            if pixmap.isNull():  #
                logger.warning(f"Failed to load image: {full_path}");  #
                continue  #

            pixmap_scaled = pixmap.scaled(view_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,  #
                                          Qt.TransformationMode.SmoothTransformation)  #
            item = QGraphicsPixmapItem(pixmap_scaled)  #
            item.setPos((view_rect.width() - pixmap_scaled.width()) / 2,  #
                        (view_rect.height() - pixmap_scaled.height()) / 2)  #
            item.setZValue(i)  #
            self.scene.addItem(item)  #

        self.scene.setSceneRect(QRectF(view_rect))  #
        logger.debug("Image display complete.")  #

        if self.current_text:  #
            self.displayText(self.current_text, self.current_style_options)  #

    def displayText(self, text_to_display: str, style_options: dict = None):
        self.clearText()  #

        self.current_text = text_to_display  #
        self.current_style_options = style_options if isinstance(style_options, dict) else {}  #

        if not text_to_display:  #
            logger.debug("displayText called with empty text, clearing.")  #
            return  #

        logger.debug(f"Displaying text: '{text_to_display[:50]}...' with options: {self.current_style_options}")  #

        font_family = self.current_style_options.get("font_family", DEFAULT_FONT_FAMILY)  #
        font_size = self.current_style_options.get("font_size", DEFAULT_FONT_SIZE)  #
        font_color_hex = self.current_style_options.get("font_color", DEFAULT_FONT_COLOR)  #
        bg_color_hex = self.current_style_options.get("background_color", DEFAULT_BACKGROUND_COLOR)  #
        bg_alpha_int = self.current_style_options.get("background_alpha", DEFAULT_BACKGROUND_ALPHA)  #
        h_align = self.current_style_options.get("text_align", DEFAULT_TEXT_ALIGN)  #
        v_align = self.current_style_options.get("text_vertical_align", DEFAULT_TEXT_VERTICAL_ALIGN)  #
        fit_to_width = self.current_style_options.get("fit_to_width", DEFAULT_FIT_TO_WIDTH)  #

        font = QFont(font_family, font_size)  #
        font.setBold(True)  #
        q_bg_color = QColor(bg_color_hex)  #
        q_bg_color.setAlpha(bg_alpha_int)  #
        bg_color_rgba_css = f"rgba({q_bg_color.red()}, {q_bg_color.green()}, {q_bg_color.blue()}, {q_bg_color.alphaF():.3f})"  #
        escaped_text_with_br = html.escape(text_to_display).replace("\n", "<br/>")  #

        self.text_item = QGraphicsTextItem()  #
        self.text_item.setFont(font)  #

        text_document = self.text_item.document()

        # FIX FOR DOUBLE BACKGROUND (PART 1 - Document Frame)
        root_frame_format = text_document.rootFrame().frameFormat()
        root_frame_format.setBackground(QBrush(Qt.GlobalColor.transparent))
        text_document.rootFrame().setFrameFormat(root_frame_format)

        # REMOVED FAULTY PALETTE FIX - QTEXTDOCUMENT HAS NO PALETTE()
        # # --- FIX FOR DOUBLE BACKGROUND (PART 2 - Document Palette Base) ---
        # doc_palette = text_document.palette()
        # doc_palette.setBrush(QPalette.ColorRole.Base, QBrush(Qt.GlobalColor.transparent))
        # text_document.setPalette(doc_palette)

        view_rect = self.view.viewport().rect()  #
        if view_rect.isEmpty(): view_rect = self.rect()  #
        if view_rect.isEmpty():  #
            logger.warning("View or window rect is empty, cannot display text properly.")  #
            return  #

        text_item_actual_width = 0  #
        width_style_css = ""  #

        if fit_to_width:  #
            text_item_actual_width = view_rect.width() - 2 * TEXT_MARGIN_HORIZONTAL  #
            self.text_item.setTextWidth(text_item_actual_width)  #
            width_style_css = f"width: {text_item_actual_width}px; box-sizing: border-box;"  #
        else:
            self.text_item.setTextWidth(-1)  #

        html_content = (  #
            f"<div style='"
            f"background-color: {bg_color_rgba_css}; "  #
            f"color: {font_color_hex}; "  #
            f"padding: {TEXT_PADDING_CSS}; "  #
            f"border-radius: {TEXT_BORDER_RADIUS_CSS}; "  #
            f"text-align: {h_align}; "  #
            f"{width_style_css}'"  #
            f">{escaped_text_with_br}</div>"  #
        )
        self.text_item.setHtml(html_content)  #

        # FIX FOR CHARACTER-LEVEL BACKGROUND ON FIRST LINE (Issue 1)
        # This attempts to clear any default character background on the first text block.
        first_block = text_document.firstBlock()
        if first_block.isValid():
            cursor = QTextCursor(first_block)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)

            char_format_for_bg_clear = QTextCharFormat()
            char_format_for_bg_clear.setBackground(QBrush(Qt.GlobalColor.transparent))
            cursor.mergeCharFormat(char_format_for_bg_clear)

        # FIX FOR HORIZONTAL ALIGNMENT (Issue 2)
        # Apply QTextOption alignment *after* HTML content is set
        doc_option = text_document.defaultTextOption()
        if h_align == "left":  #
            doc_option.setAlignment(Qt.AlignmentFlag.AlignLeft)  #
        elif h_align == "center":  #
            doc_option.setAlignment(Qt.AlignmentFlag.AlignHCenter)  #
        elif h_align == "right":  #
            doc_option.setAlignment(Qt.AlignmentFlag.AlignRight)  #
        text_document.setDefaultTextOption(doc_option)

        text_bounding_rect = self.text_item.boundingRect()  #

        pos_x = 0  #
        if fit_to_width:  #
            pos_x = TEXT_MARGIN_HORIZONTAL  #
        else:
            pos_x = (view_rect.width() - text_bounding_rect.width()) / 2  #

        pos_y = 0  #
        if v_align == "top":  #
            pos_y = TEXT_MARGIN_VERTICAL_TOP_BOTTOM  #
        elif v_align == "middle":  #
            pos_y = (view_rect.height() - text_bounding_rect.height()) / 2  #
        elif v_align == "bottom":  #
            pos_y = view_rect.height() - text_bounding_rect.height() - TEXT_MARGIN_VERTICAL_TOP_BOTTOM  #

        self.text_item.setPos(pos_x, pos_y)  #
        self.text_item.setZValue(1000)  #
        self.scene.addItem(self.text_item)  #
        logger.debug(  #
            f"Text item added. Pos: ({pos_x:.1f}, {pos_y:.1f}), Size: ({text_bounding_rect.width():.1f}, {text_bounding_rect.height():.1f})")  #

    def clearText(self):
        if self.text_item and self.text_item in self.scene.items():  #
            logger.debug("Clearing text item.")  #
            self.scene.removeItem(self.text_item)  #
            self.text_item = None  #

    def clear_display(self):
        logger.info("Clearing display (images and text).")  #
        self.clearText()  #
        self.current_text = None  #
        self.current_style_options = {}  #

        for item in self.scene.items():  #
            if isinstance(item, QGraphicsPixmapItem):  #
                self.scene.removeItem(item)  #
        self.current_layers = []  #

    def resizeEvent(self, event):
        super().resizeEvent(event)  #
        logger.debug("Resize event, re-rendering content.")  #
        self.display_images(self.current_layers)  #

    def showEvent(self, event):
        super().showEvent(event)  #
        logger.debug("Show event, re-rendering content if needed.")  #
        self.display_images(self.current_layers)  #