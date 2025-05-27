# myapp/gui/thumbnail_generator.py
import os
import logging
# --- MODIFIED: Added QPen ---
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QFont, QPen
# --- END MODIFIED ---
from PySide6.QtCore import Qt, QPoint, QSize
# --- MODIFIED: Added get_icon_file_path ---
from ..utils.paths import get_media_file_path, get_icon_file_path
# --- END MODIFIED ---

logger = logging.getLogger(__name__)

THUMBNAIL_IMAGE_WIDTH = 120
THUMBNAIL_IMAGE_HEIGHT = 90
INDICATOR_AREA_HEIGHT = 25
INDICATOR_ICON_SIZE = 16
TOTAL_ICON_WIDTH = THUMBNAIL_IMAGE_WIDTH
TOTAL_ICON_HEIGHT = THUMBNAIL_IMAGE_HEIGHT + INDICATOR_AREA_HEIGHT

def _draw_error_placeholder(target_pixmap):
    """
    Draws an error placeholder (icon or 'X') on the target_pixmap.
    """
    painter = QPainter(target_pixmap)
    try:
        error_icon_path = get_icon_file_path("image_error.png")
        if error_icon_path and os.path.exists(error_icon_path):
            error_pixmap = QPixmap(error_icon_path)
            if not error_pixmap.isNull():
                # Scale and center the error icon
                scaled = error_pixmap.scaled(
                    target_pixmap.width() // 2, target_pixmap.height() // 2,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                x = (target_pixmap.width() - scaled.width()) / 2
                y = (target_pixmap.height() - scaled.height()) / 2
                painter.drawPixmap(QPoint(int(x), int(y)), scaled)
                logger.debug("Drew error icon as thumbnail placeholder.")
                painter.end()
                return # Success
    except Exception as e:
        logger.error(f"Failed to load or draw error icon, falling back to 'X': {e}")

    # Fallback: Draw a red 'X' if icon fails or isn't present
    logger.debug("Drawing 'X' as thumbnail placeholder.")
    pen = QPen(Qt.GlobalColor.red)
    pen.setWidth(4)
    painter.setPen(pen)
    rect = target_pixmap.rect().adjusted(20, 15, -20, -15) # Add some margin
    painter.drawLine(rect.topLeft(), rect.bottomRight())
    painter.drawLine(rect.topRight(), rect.bottomLeft())
    painter.end()


def create_composite_thumbnail(slide_data, slide_index, indicator_icons):
    """
    Creates a composite QIcon for a slide, including a visual representation
    and indicators for duration and looping.
    """
    logger.debug(f"Creating thumbnail for slide index {slide_index}, data: {slide_data.get('layers', [])[:1]}")
    canvas_pixmap = QPixmap(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)
    canvas_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # 1. Draw the main image thumbnail
    image_part_pixmap = QPixmap(THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT)
    image_part_pixmap.fill(Qt.GlobalColor.darkGray)  # Background for the image part

    layers = slide_data.get("layers", [])
    image_drawn_successfully = False # Flag to track success

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
                    image_drawn_successfully = True # Mark as success
                    logger.debug(f"Successfully rendered image {first_image_filename} to thumbnail.")
                else:
                    # File exists, but QPixmap couldn't load it (corrupted/unsupported?)
                    logger.warning(f"QPixmap is null for image path: {image_path}. Using placeholder.")
            except (OSError, IOError) as e:
                logger.error(f"OS/IO Error loading or scaling thumbnail image {image_path}: {e}", exc_info=True)
            except Exception as e:
                logger.critical(f"Unexpected error loading/scaling thumbnail image {image_path}: {e}", exc_info=True)
        else:
            # File doesn't exist
            logger.warning(f"Thumbnail image not found at path: {image_path}. Using placeholder.")
    else:
        # No layers defined for this slide
        logger.debug(f"Slide {slide_index + 1} has no layers. Using placeholder.")


    # If image wasn't drawn for any reason, draw the placeholder
    if not image_drawn_successfully:
        _draw_error_placeholder(image_part_pixmap)

    painter.drawPixmap(0, 0, image_part_pixmap)

    # 2. Draw indicator area (This part remains the same)
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

    if loop_target > 0 and duration > 0 and not pix_loop.isNull():
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