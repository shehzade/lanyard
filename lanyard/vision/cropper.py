import io
from pathlib import Path

from PIL import Image, ImageOps

from lanyard.vision.models import BoundingBox


def crop_badge(
    image_bytes: bytes,
    box: BoundingBox,
    output_path: Path,
    padding_percent: float = 0.10,
) -> Path | None:
    try:
        raw_image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(raw_image)

        width, height = image.size
        if width <= 0 or height <= 0:
            return None

        ymin = max(0, min(1000, box.ymin))
        xmin = max(0, min(1000, box.xmin))
        ymax = max(0, min(1000, box.ymax))
        xmax = max(0, min(1000, box.xmax))

        if ymax <= ymin or xmax <= xmin:
            return None

        top = int((ymin / 1000.0) * height)
        left = int((xmin / 1000.0) * width)
        bottom = int((ymax / 1000.0) * height)
        right = int((xmax / 1000.0) * width)

        box_w = right - left
        box_h = bottom - top

        pad_x = int(box_w * padding_percent)
        pad_y = int(box_h * padding_percent)

        crop_left = max(0, left - pad_x)
        crop_top = max(0, top - pad_y)
        crop_right = min(width, right + pad_x)
        crop_bottom = min(height, bottom + pad_y)

        cropped = image.crop((crop_left, crop_top, crop_right, crop_bottom))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() in [".jpg", ".jpeg"]:
            cropped.convert("RGB").save(output_path, "JPEG", quality=95)
        else:
            cropped.save(output_path)

        return output_path
    except Exception:
        return None
