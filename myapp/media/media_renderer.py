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
    QFont, QTextOption  # Added QTextOption
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
TEXT_MARGIN_HORIZONTAL = 30  # Horizontal margin from view edge if fit_to_width or for x-pos calc
TEXT_MARGIN_VERTICAL_TOP_BOTTOM = 50  # Vertical margin from view edge for top/bottom align
TEXT_PADDING_CSS = "15px"  # CSS padding inside the text background box
TEXT_BORDER_RADIUS_CSS = "10px"  # CSS border radius for the text background box


class MediaRenderer(QMainWindow):
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

        self.current_layers = []
        self.text_item = None
        self.current_text = None
        self.current_style_options = {}  # To store style options for resize/reshow
        logger.debug("MediaRenderer initialized.")

    def display_images(self, image_filenames):
        logger.debug(f"Displaying images: {image_filenames}")

        # Store and remove current text item before clearing scene for images
        # It will be re-added if self.current_text is still set
        temp_text_item = self.text_item
        if temp_text_item and temp_text_item in self.scene.items():
            self.scene.removeItem(temp_text_item)
            # self.text_item = None # displayText will create a new one

        # Clear only QGraphicsPixmapItems (image layers)
        for item in self.scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                self.scene.removeItem(item)

        self.current_layers = image_filenames

        if not image_filenames:
            logger.info("No images to display for the current slide.")
            # If text exists, re-display it even without images
            if self.current_text:
                self.displayText(self.current_text, self.current_style_options)
            return

        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty(): view_rect = self.rect()
        if view_rect.isEmpty():
            logger.warning("View or window rect is empty, cannot scale images.")
            if self.current_text:  # Still try to show text
                self.displayText(self.current_text, self.current_style_options)
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

        # Re-display text if it exists, using stored style options
        if self.current_text:
            self.displayText(self.current_text, self.current_style_options)

    def displayText(self, text_to_display: str, style_options: dict = None):
        self.clearText()  # Clear any existing text item first

        self.current_text = text_to_display  # Store for potential redraws
        self.current_style_options = style_options if isinstance(style_options, dict) else {}

        if not text_to_display:
            logger.debug("displayText called with empty text, clearing.")
            return

        logger.debug(f"Displaying text: '{text_to_display[:50]}...' with options: {self.current_style_options}")

        # Get style values or defaults
        font_family = self.current_style_options.get("font_family", DEFAULT_FONT_FAMILY)
        font_size = self.current_style_options.get("font_size", DEFAULT_FONT_SIZE)
        font_color_hex = self.current_style_options.get("font_color", DEFAULT_FONT_COLOR)

        bg_color_hex = self.current_style_options.get("background_color", DEFAULT_BACKGROUND_COLOR)
        bg_alpha_int = self.current_style_options.get("background_alpha", DEFAULT_BACKGROUND_ALPHA)  # 0-255

        h_align = self.current_style_options.get("text_align", DEFAULT_TEXT_ALIGN)
        v_align = self.current_style_options.get("text_vertical_align", DEFAULT_TEXT_VERTICAL_ALIGN)
        fit_to_width = self.current_style_options.get("fit_to_width", DEFAULT_FIT_TO_WIDTH)

        # Prepare QFont
        font = QFont(font_family, font_size)
        font.setBold(True)  # Defaulting to bold as per original style

        # Prepare background color with alpha for CSS
        q_bg_color = QColor(bg_color_hex)
        q_bg_color.setAlpha(bg_alpha_int)  # QColor takes 0-255 alpha
        bg_color_rgba_css = f"rgba({q_bg_color.red()}, {q_bg_color.green()}, {q_bg_color.blue()}, {q_bg_color.alphaF():.3f})"

        # Prepare text: escape special HTML characters and convert \n to <br/>
        escaped_text_with_br = html.escape(text_to_display).replace("\n", "<br/>")

        self.text_item = QGraphicsTextItem()
        self.text_item.setFont(font)  # Set font on the item

        view_rect = self.view.viewport().rect()
        if view_rect.isEmpty(): view_rect = self.rect()
        if view_rect.isEmpty():
            logger.warning("View or window rect is empty, cannot display text properly.")
            return

        # Set text width for wrapping and internal alignment
        text_item_actual_width = 0
        width_style_css = ""  # For the HTML div background

        if fit_to_width:
            text_item_actual_width = view_rect.width() - 2 * TEXT_MARGIN_HORIZONTAL
            self.text_item.setTextWidth(text_item_actual_width)
            # The HTML div width should match the text item width for the background
            width_style_css = f"width: {text_item_actual_width}px; box-sizing: border-box;"
        else:
            self.text_item.setTextWidth(-1)  # Auto-width based on content

        # Set horizontal alignment for the text document within QGraphicsTextItem
        # This works in conjunction with setTextWidth
        doc_option = self.text_item.document().defaultTextOption()
        if h_align == "left":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignLeft)
        elif h_align == "center":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        elif h_align == "right":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.text_item.document().setDefaultTextOption(doc_option)

        # Construct HTML for styling the div (background, text color, padding, etc.)
        # Note: QGraphicsTextItem's HTML subset might not support all CSS perfectly.
        # text-align in CSS div is less critical if QTextOption is set, but can be kept for robustness.
        html_content = (
            f"<div style='"
            f"background-color: {bg_color_rgba_css}; "
            f"color: {font_color_hex}; "  # Font color
            f"padding: {TEXT_PADDING_CSS}; "
            f"border-radius: {TEXT_BORDER_RADIUS_CSS}; "
            f"text-align: {h_align}; "  # HTML text-align
            f"{width_style_css}'"  # Width style for the div
            f">{escaped_text_with_br}</div>"
        )
        self.text_item.setHtml(html_content)

        # BoundingRect needs to be calculated AFTER content and width are set
        text_bounding_rect = self.text_item.boundingRect()

        # Calculate X position
        pos_x = 0
        if fit_to_width:
            # Text item itself is positioned at the margin, internal text aligns within its width
            pos_x = TEXT_MARGIN_HORIZONTAL
        else:
            # Center the whole text item (including its background div)
            pos_x = (view_rect.width() - text_bounding_rect.width()) / 2

        # Calculate Y position
        pos_y = 0
        if v_align == "top":
            pos_y = TEXT_MARGIN_VERTICAL_TOP_BOTTOM
        elif v_align == "middle":
            pos_y = (view_rect.height() - text_bounding_rect.height()) / 2
        elif v_align == "bottom":  # Default
            pos_y = view_rect.height() - text_bounding_rect.height() - TEXT_MARGIN_VERTICAL_TOP_BOTTOM

        self.text_item.setPos(pos_x, pos_y)
        self.text_item.setZValue(1000)  # Ensure text is on top of images
        self.scene.addItem(self.text_item)
        logger.debug(
            f"Text item added. Pos: ({pos_x:.1f}, {pos_y:.1f}), Size: ({text_bounding_rect.width():.1f}, {text_bounding_rect.height():.1f})")

    def clearText(self):
        if self.text_item and self.text_item in self.scene.items():
            logger.debug("Clearing text item.")
            self.scene.removeItem(self.text_item)
            self.text_item = None
        # self.current_text = None # Keep current_text for redraw on image change, clear only if explicitly told
        # self.current_style_options = {} # Keep for redraw

    def clear_display(self):
        logger.info("Clearing display (images and text).")
        self.clearText()  # Clear text specific data
        self.current_text = None  # Explicitly clear text content on full clear
        self.current_style_options = {}  # And styles

        # Clear images
        for item in self.scene.items():  # Remove any remaining items (like pixmap items)
            if isinstance(item, QGraphicsPixmapItem):
                self.scene.removeItem(item)
        self.current_layers = []
        # self.scene.clear() # This is too broad if we want to manage items carefully

    def resizeEvent(self, event):
        super().resizeEvent(event)
        logger.debug("Resize event, re-rendering content.")
        # Re-display images (which will scale them to the new view size)
        # And then re-display text using stored text and style options
        # The call to display_images will handle re-calling displayText if current_text is set
        self.display_images(self.current_layers)

    def showEvent(self, event):
        super().showEvent(event)
        logger.debug("Show event, re-rendering content if needed.")
        # Similar to resize, ensure content is properly displayed according to current state
        self.display_images(self.current_layers)