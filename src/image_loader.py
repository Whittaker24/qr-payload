"""Find and base64-encode slip images, converting HEIC to PNG as needed.

Claude's vision API accepts JPEG, PNG, GIF, and WebP only — not HEIC. Any
HEIC input must be converted to PNG before it's sent.
"""
# Standard library imports
# pathlib for path manipulation
from pathlib import Path
# base64 for base64 encoding
import base64
# io for file operations
import io
# PIL for image processing
from PIL import Image
# pillow_heif for HEIC/HEIF conversion
import pillow_heif

# CHANGED: register pillow_heif as a Pillow plugin once, at import time, so
# Image.open() can read HEIC/HEIF directly. Simpler and safer than manually
# calling pillow_heif.open_heif() + Image.frombytes(): that path assumes
# image rows are tightly packed, but HEIF decoders can pad each row to an
# alignment boundary (heif.stride) — frombytes() without accounting for
# that can produce a skewed image. register_heif_opener() lets Pillow
# handle that internally instead.
pillow_heif.register_heif_opener()

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".heif"}
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def find_images(folder: str | Path) -> list[Path]:
    """Find image files in a folder.

    Args:
        folder: Path to a directory to search for slip images.

    Returns:
        A list of Path objects for files in `folder` with a supported
        image extension (see SUPPORTED_EXTENSIONS), including HEIC/HEIF —
        conversion happens later in encode_image(), not here.

    # `folder`'s contents (non-recursive is fine for the PoC)
    # and filter to SUPPORTED_EXTENSIONS. Match extensions case-insensitively
    # (e.g. ".PNG" and ".png" should both match) — phone screenshots often
    # have uppercase extensions

    """
    folder = Path(folder)
    images = []
    for path in folder.iterdir():
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            images.append(path)
    return images


def encode_image(path: str | Path) -> tuple[str, str]:
    """Base64-encode an image file for a vision API content block.

    If `path` is HEIC/HEIF, convert it to PNG in memory first (Claude's
    vision API doesn't accept HEIC) — use `pillow-heif` to register a HEIF
    opener with Pillow, then re-save as PNG into a BytesIO buffer before
    encoding. Otherwise, read the file's bytes directly.

    Args:
        path: Path to a single image file.

    Returns:
        A (base64_data, media_type) tuple, e.g.
        ("iVBORw0KG...", "image/png"), ready to drop into an API image
        content block's `source.data` / `source.media_type`.

 
    # - if path suffix is .heic/.heif: open with pillow-heif + Pillow,
    #   save as PNG to an io.BytesIO buffer, base64-encode the buffer's
    #   bytes, media_type = "image/png"
    # - else: read the file's raw bytes, base64-encode them, media_type
    #   based on the actual extension (map .jpg/.jpeg -> "image/jpeg",
    #   .png -> "image/png", etc.)
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".heic", ".heif"}:
        # CHANGED: was `with pillow_heif.open_heif(path) as heif: ... Image.frombytes(...)`.
        # HeifFile doesn't support the `with` statement — that raised
        # `TypeError: 'HeifFile' object does not support the context manager
        # protocol` on every HEIC upload (confirmed by testing it directly).
        # Now that register_heif_opener() is called at import time, Image.open()
        # reads HEIC/HEIF the same as any other format, so no manual
        # frombytes()/stride handling is needed at all.
        image = Image.open(path)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8"), "image/png"
    else:
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return encoded, MEDIA_TYPES[suffix]
