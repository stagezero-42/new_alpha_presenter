# myapp/gui/thumbnail_generator.py
import os
import logging  # Import logging
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QFont
from PySide6.QtCore import Qt, QPoint, QSize
from ..utils.paths import get_media_file_path

# Get the logger for this specific module
logger = logging.getLogger(__name__)

# Constants for thumbnail generation
THUMBNAIL_IMAGE_WIDTH = 120
THUMBNAIL_IMAGE_HEIGHT = 90
INDICATOR_AREA_HEIGHT = 25
INDICATOR_ICON_SIZE = 16
TOTAL_ICON_WIDTH = THUMBNAIL_IMAGE_WIDTH
TOTAL_ICON_HEIGHT = THUMBNAIL_IMAGE_HEIGHT + INDICATOR_AREA_HEIGHT


def create_composite_thumbnail(slide_data, slide_index, indicator_icons):
    """
    Creates a composite QIcon for a slide, including a visual representation
    and indicators for duration and looping.

    Args:
        slide_data (dict): The dictionary containing data for the slide.
        slide_index (int): The 0-based index of the slide.
        indicator_icons (dict): A dictionary containing pre-loaded QPixmaps
                                 for 'slide', 'timer', and 'loop'.

    Returns:
        QIcon: The generated composite icon.
    """
    logger.debug(f"Creating thumbnail for slide index {slide_index}, data: {slide_data.get('layers', [])[:1]}") # Log first layer for brevity
    canvas_pixmap = QPixmap(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)
    canvas_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # 1. Draw the main image thumbnail
    image_part_pixmap = QPixmap(THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT)
    image_part_pixmap.fill(Qt.GlobalColor.darkGray)  # Background for the image part

    layers = slide_data.get("layers", [])
    if layers:
        first_image_filename = layers[0]
        image_path = get_media_file_path(first_image_filename) #
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
                    logger.debug(f"Successfully rendered image {first_image_filename} to thumbnail.")
                else:
                    logger.warning(f"QPixmap is null for image path: {image_path}. Thumbnail will use background.")
            except Exception as e:
                logger.error(f"Error loading or scaling thumbnail image {image_path}: {e}", exc_info=True)
        else:
            logger.warning(f"Thumbnail image not found at path: {image_path}. Using background.")

    painter.drawPixmap(0, 0, image_part_pixmap)

    # 2. Draw indicator area
    indicator_y_start = THUMBNAIL_IMAGE_HEIGHT + 2
    current_x = 5

    font = painter.font()
    font.setPointSize(9)
    painter.setFont(font)
    painter.setPen(QColor(Qt.GlobalColor.black))

    pix_slide = indicator_icons.get("slide", QPixmap())
    pix_timer = indicator_icons.get("timer", QPixmap())
    pix_loop = indicator_icons.get("loop", QPixmap())

    if not pix_slide.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_slide)
    current_x += INDICATOR_ICON_SIZE + 2

    slide_num_text = str(slide_index + 1)
    fm = painter.fontMetrics()
    text_rect = fm.boundingRect(slide_num_text)
    painter.drawText(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - text_rect.height()) // 2 + text_rect.height() - fm.descent(), slide_num_text)
    current_x += text_rect.width() + 7

    duration = slide_data.get("duration", 0)
    loop_target = slide_data.get("loop_to_slide", 0)

    if duration > 0 and not pix_timer.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_timer)
        current_x += INDICATOR_ICON_SIZE + 7

    if loop_target > 0 and duration > 0 and not pix_loop.isNull(): # Loop icon shown only if duration > 0
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_loop)

    painter.end()
    logger.debug(f"Thumbnail creation complete for slide index {slide_index}.")
    return QIcon(canvas_pixmap)

def get_thumbnail_size():
    """Returns the QSize for the thumbnails."""
    return QSize(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)

def get_list_widget_height():
    """Returns the recommended height for the QListWidget."""
    return TOTAL_ICON_HEIGHT + 25