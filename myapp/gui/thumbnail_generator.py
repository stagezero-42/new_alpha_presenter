# myapp/gui/thumbnail_generator.py
import os
import logging
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QFont, QPen
from PySide6.QtCore import Qt, QPoint, QSize
from ..utils.paths import get_media_file_path, get_icon_file_path

logger = logging.getLogger(__name__)

THUMBNAIL_IMAGE_WIDTH = 120
THUMBNAIL_IMAGE_HEIGHT = 90
INDICATOR_AREA_HEIGHT = 25
INDICATOR_ICON_SIZE = 16 # General size for all indicator icons
TOTAL_ICON_WIDTH = THUMBNAIL_IMAGE_WIDTH
TOTAL_ICON_HEIGHT = THUMBNAIL_IMAGE_HEIGHT + INDICATOR_AREA_HEIGHT

def _draw_error_placeholder(target_pixmap):
    # ... (This function remains unchanged) ...
    painter = QPainter(target_pixmap)
    try:
        error_icon_path = get_icon_file_path("image_error.png")
        if error_icon_path and os.path.exists(error_icon_path):
            error_pixmap = QPixmap(error_icon_path)
            if not error_pixmap.isNull():
                scaled = error_pixmap.scaled(
                    target_pixmap.width() // 2, target_pixmap.height() // 2,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                x = (target_pixmap.width() - scaled.width()) / 2
                y = (target_pixmap.height() - scaled.height()) / 2
                painter.drawPixmap(QPoint(int(x), int(y)), scaled)
                logger.debug("Drew error icon as thumbnail placeholder.")
                painter.end()
                return
    except Exception as e:
        logger.error(f"Failed to load or draw error icon, falling back to 'X': {e}")

    logger.debug("Drawing 'X' as thumbnail placeholder.")
    pen = QPen(Qt.GlobalColor.red)
    pen.setWidth(4)
    painter.setPen(pen)
    rect = target_pixmap.rect().adjusted(20, 15, -20, -15)
    painter.drawLine(rect.topLeft(), rect.bottomRight())
    painter.drawLine(rect.topRight(), rect.bottomLeft())
    painter.end()


# --- MODIFIED: Added has_text_overlay parameter ---
def create_composite_thumbnail(slide_data, slide_index, indicator_icons, has_text_overlay=False):
# --- END MODIFIED ---
    """
    Creates a composite QIcon for a slide, including a visual representation
    and indicators for duration, looping, and text.
    """
    logger.debug(f"Creating thumbnail for slide index {slide_index}, text: {has_text_overlay}, data: {slide_data.get('layers', [])[:1]}")
    canvas_pixmap = QPixmap(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)
    canvas_pixmap.fill(Qt.GlobalColor.transparent) # Use transparent background

    painter = QPainter(canvas_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # 1. Draw the main image thumbnail
    image_part_pixmap = QPixmap(THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT)
    image_part_pixmap.fill(Qt.GlobalColor.darkGray)

    layers = slide_data.get("layers", [])
    image_drawn_successfully = False

    if layers:
        first_image_filename = layers[0]
        image_path = get_media_file_path(first_image_filename)
        logger.debug(f"Attempting to load thumbnail image: {image_path}")

        if os.path.exists(image_path):
            try:
                original_pixmap = QPixmap(image_path)
                if not original_pixmap.isNull():
                    scaled_pixmap = original_pixmap.scaled(
                        THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    x_img = (THUMBNAIL_IMAGE_WIDTH - scaled_pixmap.width()) / 2
                    y_img = (THUMBNAIL_IMAGE_HEIGHT - scaled_pixmap.height()) / 2
                    img_painter = QPainter(image_part_pixmap)
                    img_painter.drawPixmap(QPoint(int(x_img), int(y_img)), scaled_pixmap)
                    img_painter.end()
                    image_drawn_successfully = True
                    logger.debug(f"Successfully rendered image {first_image_filename} to thumbnail.")
                else:
                    logger.warning(f"QPixmap is null for image path: {image_path}. Using placeholder.")
            except Exception as e:
                logger.critical(f"Unexpected error loading/scaling thumbnail image {image_path}: {e}", exc_info=True)
        else:
            logger.warning(f"Thumbnail image not found at path: {image_path}. Using placeholder.")
    else:
        logger.debug(f"Slide {slide_index + 1} has no layers. Using placeholder.")

    if not image_drawn_successfully:
        _draw_error_placeholder(image_part_pixmap)

    painter.drawPixmap(0, 0, image_part_pixmap)

    # 2. Draw indicator area
    indicator_y_start = THUMBNAIL_IMAGE_HEIGHT + 2 # Small gap
    current_x = 5
    icon_spacing = 2
    text_spacing = 7

    font = painter.font()
    font.setPointSize(9) # Small font for text indicators
    painter.setFont(font)
    painter.setPen(QColor(Qt.GlobalColor.black)) # Text color for indicators

    # Load icons from the provided dict
    pix_slide = indicator_icons.get("slide", QPixmap())
    pix_timer = indicator_icons.get("timer", QPixmap())
    pix_loop = indicator_icons.get("loop", QPixmap())
    # --- NEW: Load text icon ---
    pix_text_indicator = indicator_icons.get("text", QPixmap())
    # --- END NEW ---

    # Slide number
    if not pix_slide.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_slide)
    current_x += INDICATOR_ICON_SIZE + icon_spacing

    slide_num_text = str(slide_index + 1)
    fm = painter.fontMetrics()
    text_rect = fm.boundingRect(slide_num_text)
    # Vertically center text in the indicator area
    text_y = indicator_y_start + (INDICATOR_AREA_HEIGHT - text_rect.height()) // 2 + text_rect.height() - fm.descent()
    painter.drawText(current_x, text_y, slide_num_text)
    current_x += text_rect.width() + text_spacing

    # Duration icon
    duration = slide_data.get("duration", 0)
    if duration > 0 and not pix_timer.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_timer)
        current_x += INDICATOR_ICON_SIZE + text_spacing # Space after timer icon

    # Loop icon
    loop_target = slide_data.get("loop_to_slide", 0)
    if loop_target > 0 and duration > 0 and not pix_loop.isNull(): # Loop needs duration
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_loop)
        current_x += INDICATOR_ICON_SIZE + text_spacing # Space after loop icon

    # --- NEW: Text overlay indicator icon ---
    if has_text_overlay and not pix_text_indicator.isNull():
        # Position it to the right, ensure it doesn't overflow if possible
        # If other icons took up too much space, this might get cramped.
        # A more advanced layout might dynamically adjust spacing or icon presence.
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_text_indicator)
        # current_x += INDICATOR_ICON_SIZE + icon_spacing # If more icons were to follow
    # --- END NEW ---

    painter.end()
    logger.debug(f"Thumbnail creation complete for slide index {slide_index}.")
    return QIcon(canvas_pixmap)


def get_thumbnail_size():
    """Returns the QSize for the thumbnails."""
    return QSize(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)


def get_list_widget_height():
    """Returns the recommended height for the QListWidget."""
    return TOTAL_ICON_HEIGHT + 25 # Add some padding