from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

Image = None
ImageOps = None
ImageSequence = None
RESAMPLE_LANCZOS = None


@dataclass(slots=True)
class Frame:
    rgb_bytes: bytes
    duration_ms: int


def _load_pillow() -> None:
    global Image, ImageOps, ImageSequence, RESAMPLE_LANCZOS
    if Image is not None:
        return

    try:
        from PIL import Image as pil_image
        from PIL import ImageOps as pil_image_ops
        from PIL import ImageSequence as pil_image_sequence
    except ModuleNotFoundError as exc:
        raise RuntimeError("Pillow is required for image and GIF support. Install it with: pip install Pillow") from exc

    Image = pil_image
    ImageOps = pil_image_ops
    ImageSequence = pil_image_sequence
    try:
        RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
    except AttributeError:
        RESAMPLE_LANCZOS = Image.LANCZOS


def resize_image(image: "Image.Image", width: int, height: int, fit_mode: str = "stretch") -> "Image.Image":
    _load_pillow()
    rgb = image.convert("RGB")
    if fit_mode == "stretch":
        return rgb.resize((width, height), RESAMPLE_LANCZOS)
    if fit_mode == "contain":
        contained = ImageOps.contain(rgb, (width, height), RESAMPLE_LANCZOS)
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        x = (width - contained.width) // 2
        y = (height - contained.height) // 2
        canvas.paste(contained, (x, y))
        return canvas
    if fit_mode == "cover":
        return ImageOps.fit(rgb, (width, height), RESAMPLE_LANCZOS)
    raise ValueError(f"Unsupported fit mode: {fit_mode}")


def load_image_frame(path: str | Path, width: int, height: int, fit_mode: str = "stretch") -> Frame:
    _load_pillow()
    image = Image.open(path)
    resized = resize_image(image, width, height, fit_mode=fit_mode)
    return Frame(rgb_bytes=resized.tobytes(), duration_ms=0)


def iter_gif_frames(path: str | Path, width: int, height: int, fit_mode: str = "stretch") -> Iterator[Frame]:
    _load_pillow()
    image = Image.open(path)
    for frame in ImageSequence.Iterator(image):
        duration_ms = int(frame.info.get("duration", 100))
        resized = resize_image(frame, width, height, fit_mode=fit_mode)
        yield Frame(rgb_bytes=resized.tobytes(), duration_ms=max(duration_ms, 20))


def make_test_pattern(width: int, height: int, step: int) -> bytes:
    pixels = bytearray(width * height * 3)
    pos = 0
    for y in range(height):
        for x in range(width):
            r = (x * 255) // max(1, width - 1)
            g = (y * 255) // max(1, height - 1)
            b = ((x + y + step * 8) * 255) // max(1, width + height + 63)
            pixels[pos] = (r + step * 7) & 0xFF
            pixels[pos + 1] = (g + step * 11) & 0xFF
            pixels[pos + 2] = b & 0xFF
            pos += 3
    return bytes(pixels)
