# myapp/gui/thumbnail_generator.py
import os
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QFont
from PySide6.QtCore import Qt, QPoint, QSize
# --- NEW IMPORT ---
from ..utils.paths import get_media_file_path
# --- END NEW IMPORT ---

# Constants...
THUMBNAIL_IMAGE_WIDTH = 120
THUMBNAIL_IMAGE_HEIGHT = 90
INDICATOR_AREA_HEIGHT = 25
INDICATOR_ICON_SIZE = 16
TOTAL_ICON_WIDTH = THUMBNAIL_IMAGE_WIDTH
TOTAL_ICON_HEIGHT = THUMBNAIL_IMAGE_HEIGHT + INDICATOR_AREA_HEIGHT

# --- MODIFIED: Removed media_base_path argument ---
def create_composite_thumbnail(slide_data, slide_index, indicator_icons):
    """
    Creates a composite QIcon for a slide.

    Args:
        slide_data (dict): The dictionary containing data for the slide.
        slide_index (int): The 0-based index of the slide.
        indicator_icons (dict): Pre-loaded QPixmaps for indicators.

    Returns:
        QIcon: The generated composite icon.
    """
# --- END MODIFIED ---
    canvas_pixmap = QPixmap(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)
    canvas_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    image_part_pixmap = QPixmap(THUMBNAIL_IMAGE_WIDTH, THUMBNAIL_IMAGE_HEIGHT)
    image_part_pixmap.fill(Qt.GlobalColor.darkGray)

    layers = slide_data.get("layers", [])
    if layers:
        first_image_filename = layers[0]
        # --- MODIFIED: Use get_media_file_path ---
        image_path = get_media_file_path(first_image_filename)
        # --- END MODIFIED ---
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
                else:
                    print(f"Warning: QPixmap is null for {image_path}")
            except Exception as e:
                print(f"Error loading thumbnail {image_path}: {e}")

    painter.drawPixmap(0, 0, image_part_pixmap)

    # ... (rest of the drawing code remains the same) ...
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
    return QIcon(canvas_pixmap)

def get_thumbnail_size():
    """Returns the QSize for the thumbnails."""
    return QSize(TOTAL_ICON_WIDTH, TOTAL_ICON_HEIGHT)

def get_list_widget_height():
    """Returns the recommended height for the QListWidget."""
    return TOTAL_ICON_HEIGHT + 25