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
INDICATOR_ICON_SIZE = 16
TOTAL_ICON_WIDTH = THUMBNAIL_IMAGE_WIDTH
TOTAL_ICON_HEIGHT = THUMBNAIL_IMAGE_HEIGHT + INDICATOR_AREA_HEIGHT


def _draw_error_placeholder(target_pixmap):
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
                painter.end()
                return
    except Exception as e:
        logger.error(f"Failed to load or draw error icon: {e}")

    pen = QPen(Qt.GlobalColor.red);
    pen.setWidth(4)
    painter.setPen(pen)
    rect = target_pixmap.rect().adjusted(20, 15, -20, -15)
    painter.drawLine(rect.topLeft(), rect.bottomRight())
    painter.drawLine(rect.topRight(), rect.bottomLeft())
    painter.end()


def create_composite_thumbnail(slide_data, slide_index, indicator_icons,
                               has_text_overlay=False,
                               has_audio_program=False,
                               audio_program_loops=False):
    logger.debug(f"Creating thumbnail for slide {slide_index}, text: {has_text_overlay}, audio: {has_audio_program}")
    canvas_pixmap = QPixmap(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)
    canvas_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    image_part_pixmap = QPixmap(THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT)
    image_part_pixmap.fill(Qt.GlobalColor.darkGray)
    image_drawn_successfully = False

    is_video_slide = bool(slide_data.get("video_path"))

    if is_video_slide:
        thumbnail_image_filename = slide_data.get("thumbnail_path")
    else:
        layers = slide_data.get("layers", [])
        thumbnail_image_filename = layers[0] if layers else None

    if thumbnail_image_filename:
        image_path = get_media_file_path(thumbnail_image_filename)
        if os.path.exists(image_path):
            try:
                original_pixmap = QPixmap(image_path)
                if not original_pixmap.isNull():
                    scaled_pixmap = original_pixmap.scaled(
                        THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT,
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    )
                    x_img = (THUMBNAIL_IMAGE_WIDTH - scaled_pixmap.width()) / 2
                    y_img = (THUMBNAIL_IMAGE_HEIGHT - scaled_pixmap.height()) / 2
                    img_painter = QPainter(image_part_pixmap)
                    img_painter.drawPixmap(QPoint(int(x_img), int(y_img)), scaled_pixmap)
                    img_painter.end()
                    image_drawn_successfully = True
            except Exception as e:
                logger.critical(f"Error loading/scaling thumbnail image {image_path}: {e}", exc_info=True)
        else:
            logger.warning(f"Thumbnail image not found: {image_path}.")
    else:
        logger.debug(f"Slide {slide_index + 1} has no layers or thumbnail.")

    if not image_drawn_successfully: _draw_error_placeholder(image_part_pixmap)
    painter.drawPixmap(0, 0, image_part_pixmap)

    indicator_y_start = THUMBNAIL_IMAGE_HEIGHT + 2
    current_x = 5
    icon_spacing = 2
    text_spacing = 7
    font = painter.font();
    font.setPointSize(9);
    painter.setFont(font)
    painter.setPen(QColor(Qt.GlobalColor.black))

    pix_slide = indicator_icons.get("slide", QPixmap())
    pix_timer = indicator_icons.get("timer", QPixmap())
    pix_loop_slide = indicator_icons.get("loop", QPixmap())
    pix_text = indicator_icons.get("text", QPixmap())
    pix_audio = indicator_icons.get("audio", QPixmap())
    pix_loop_audio = indicator_icons.get("loop", QPixmap())
    pix_video = indicator_icons.get("video", QPixmap())

    # --- FIX: Use video icon for video slides, slide icon otherwise ---
    type_icon = pix_video if is_video_slide else pix_slide
    if not type_icon.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, type_icon)
    # --- END FIX ---

    current_x += INDICATOR_ICON_SIZE + icon_spacing
    slide_num_text = str(slide_index + 1)
    fm = painter.fontMetrics();
    text_rect = fm.boundingRect(slide_num_text)
    text_y = indicator_y_start + (INDICATOR_AREA_HEIGHT - text_rect.height()) // 2 + text_rect.height() - fm.descent()
    painter.drawText(current_x, text_y, slide_num_text)
    current_x += text_rect.width() + text_spacing

    duration = slide_data.get("duration", 0)
    text_timed = has_text_overlay and slide_data.get("text_overlay", {}).get("sentence_timing_enabled", False)
    if (duration > 0 or text_timed) and not pix_timer.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_timer)
        current_x += INDICATOR_ICON_SIZE + text_spacing

    loop_target = slide_data.get("loop_to_slide", 0)
    if loop_target > 0 and (duration > 0 or text_timed) and not pix_loop_slide.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2,
                           pix_loop_slide)
        current_x += INDICATOR_ICON_SIZE + text_spacing

    if has_text_overlay and not pix_text.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_text)
        current_x += INDICATOR_ICON_SIZE + text_spacing

    if has_audio_program and not pix_audio.isNull():
        painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2, pix_audio)
        current_x += INDICATOR_ICON_SIZE
        if audio_program_loops and not pix_loop_audio.isNull():
            painter.drawPixmap(current_x, indicator_y_start + (INDICATOR_AREA_HEIGHT - INDICATOR_ICON_SIZE) // 2,
                               pix_loop_audio)
            current_x += INDICATOR_ICON_SIZE

    painter.end()
    logger.debug(f"Thumbnail creation complete for slide index {slide_index}.")
    return QIcon(canvas_pixmap)


def get_thumbnail_size():
    return QSize(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)


def get_list_widget_height():
    return TOTAL_ICON_HEIGHT + 27