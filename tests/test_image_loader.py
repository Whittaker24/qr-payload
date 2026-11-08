import base64

import pytest
from PIL import Image

from src.image_loader import encode_image, find_images


def _make_image(path, fmt):
    Image.new("RGB", (4, 4), "white").save(path, format=fmt)


def test_find_images_matches_extensions_case_insensitively(tmp_path):
    _make_image(tmp_path / "a.PNG", "PNG")
    _make_image(tmp_path / "b.jpg", "JPEG")
    (tmp_path / "notes.txt").write_text("not an image")
    found = {p.name for p in find_images(tmp_path)}
    assert found == {"a.PNG", "b.jpg"}


def test_encode_png_returns_media_type_and_roundtrips(tmp_path):
    path = tmp_path / "slip.png"
    _make_image(path, "PNG")
    data, media_type = encode_image(path)
    assert media_type == "image/png"
    assert base64.b64decode(data) == path.read_bytes()


def test_encode_heic_converts_to_png(tmp_path):
    path = tmp_path / "slip.heic"
    _make_image(path, "HEIF")  # pillow-heif registers the writer too
    data, media_type = encode_image(path)
    assert media_type == "image/png"
    assert base64.b64decode(data).startswith(b"\x89PNG")


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / "slip.bmp"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="Unsupported"):
        encode_image(path)
