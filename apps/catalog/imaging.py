import io
import mimetypes
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image as PILImage

from apps.catalog.models import Image

mimetypes.add_type("image/webp", ".webp")

THUMB_WIDTH = 300
DETAIL_WIDTH = 1200


def _resize_to_width(img, target_width):
    if img.width <= target_width:
        return img.copy()
    ratio = target_width / float(img.width)
    target_height = int(img.height * ratio)
    return img.resize((target_width, target_height), PILImage.LANCZOS)


def _save_webp(img, key):
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="WEBP", quality=85)
    buffer.seek(0)
    default_storage.save(key, ContentFile(buffer.read()))


def process_and_store_image(uploaded_file, original_filename=None):
    """Generate thumb (300px) + detail (1200px) WebP derivatives and store them.

    Accepts either a Django UploadedFile or a raw file-like object; returns the
    created Image row. Used by both the admin upload endpoint and the one-time
    import_catalog_images management command.
    """
    original_filename = original_filename or getattr(uploaded_file, "name", "unknown")
    source_image = PILImage.open(uploaded_file)
    source_image.load()

    image_id = uuid.uuid4()
    detail_key = f"products/{image_id}/detail.webp"
    thumb_key = f"products/{image_id}/thumb.webp"

    detail = _resize_to_width(source_image, DETAIL_WIDTH)
    thumb = _resize_to_width(source_image, THUMB_WIDTH)

    _save_webp(detail, detail_key)
    _save_webp(thumb, thumb_key)

    return Image.objects.create(
        id=image_id,
        storage_key=detail_key,
        thumb_key=thumb_key,
        width=detail.width,
        height=detail.height,
        source=Image.SOURCE_MANUAL_UPLOAD,
        original_filename=original_filename,
    )
