"""Find and base64-encode slip images, converting HEIC to PNG as needed.

Claude's vision API accepts JPEG, PNG, GIF, and WebP only — not HEIC. Any
HEIC input must be converted to PNG before it's sent.
"""

import base64
import io
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

# Register HEIC/HEIF as a Pillow format once, at import time, so Image.open()
# reads it like any other image. (Manually decoding with pillow_heif and
# Image.frombytes() can skew the image: HEIF rows may be padded to a stride.)
pillow_heif.register_heif_opener()

HEIC_EXTENSIONS = {".heic", ".heif"}
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
SUPPORTED_EXTENSIONS = set(MEDIA_TYPES) | HEIC_EXTENSIONS


def find_images(folder: str | Path) -> list[Path]:
    """Find image files in a folder.

    Args:
        folder: Path to a directory to search for slip images.

    Returns:
        Paths of files directly in `folder` (non-recursive) with a supported
        extension, including HEIC/HEIF — conversion happens later in
        encode_image(). Extensions match case-insensitively, since phone
        screenshots often have uppercase ones (".PNG").
    """
    return [
        path
        for path in Path(folder).iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def encode_image(path: str | Path) -> tuple[str, str]:
    """Base64-encode an image file for a vision API content block.

    HEIC/HEIF is converted to PNG in memory first (honouring the EXIF
    rotation so the slip isn't sideways); other formats are read as-is.

    Args:
        path: Path to a single image file.

    Returns:
        A (base64_data, media_type) tuple, e.g. ("iVBORw0KG...", "image/png"),
        ready for an API image block's `source.data` / `source.media_type`.

    Raises:
        ValueError: If the file extension isn't supported.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in HEIC_EXTENSIONS:
        image = ImageOps.exif_transpose(Image.open(path))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8"), "image/png"

    if suffix not in MEDIA_TYPES:
        raise ValueError(f"Unsupported image type {suffix!r}: expected one of {sorted(SUPPORTED_EXTENSIONS)}")
    return base64.b64encode(path.read_bytes()).decode("utf-8"), MEDIA_TYPES[suffix]
