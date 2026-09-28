import uuid
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError, features

MAX_IMAGE_UPLOAD_BYTES = 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
OPTIMIZED_IMAGE_DIMENSION = 1600
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def unique_image_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".webp"
    model_name = instance._meta.model_name
    today = timezone.localdate()
    return f"images/{model_name}/{today:%Y/%m}/{uuid.uuid4().hex}{extension}"


def validate_image_upload(uploaded_file):
    if not uploaded_file:
        return
    if uploaded_file.size > MAX_IMAGE_UPLOAD_BYTES:
        raise ValidationError("Rasm hajmi 1 MB dan katta bo'lmasligi kerak.")

    position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
        if image_format not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError("Faqat JPEG, PNG yoki WebP rasm yuklash mumkin.")
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise ValidationError(
                f"Rasm o'lchami {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} pikseldan "
                "katta bo'lmasligi kerak."
            )
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValidationError("Yuklangan fayl yaroqli rasm emas.") from exc
    finally:
        uploaded_file.seek(position)


def optimize_image(uploaded_file):
    uploaded_file.seek(0)
    with Image.open(uploaded_file) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail(
            (OPTIMIZED_IMAGE_DIMENSION, OPTIMIZED_IMAGE_DIMENSION),
            Image.Resampling.LANCZOS,
        )

        if features.check("webp"):
            output_format = "WEBP"
            extension = ".webp"
            save_options = {"quality": 82, "method": 6}
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        elif image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            output_format = "PNG"
            extension = ".png"
            save_options = {"optimize": True}
            if image.mode not in {"RGBA", "LA"}:
                image = image.convert("RGBA")
        else:
            output_format = "JPEG"
            extension = ".jpg"
            save_options = {"quality": 82, "optimize": True, "progressive": True}
            if image.mode != "RGB":
                image = image.convert("RGB")

        output = BytesIO()
        image.save(output, format=output_format, **save_options)
        output.seek(0)
        return ContentFile(output.read(), name=f"optimized{extension}")


class OptimizedImageField(models.ImageField):
    """Reusable image field with safe names, validation, and optimization."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("upload_to", unique_image_upload_to)
        validators = list(kwargs.pop("validators", []))
        if validate_image_upload not in validators:
            validators.insert(0, validate_image_upload)
        kwargs["validators"] = validators
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        image_file = getattr(model_instance, self.attname)
        if image_file and not image_file._committed:
            validate_image_upload(image_file)
            optimized = optimize_image(image_file)
            image_file.file = optimized
            image_file.name = optimized.name
        return super().pre_save(model_instance, add)
