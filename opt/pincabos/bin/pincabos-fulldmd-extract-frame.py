#!/usr/bin/env python3
"""PinCabOS FullDMD extractor and black DMD-frame detector.

Usage:
  pincabos-fulldmd-extract-frame.py source.directb2s output.png output.env
"""
from __future__ import annotations

import base64
import html
import math
import re
import struct
import sys
import zlib
from pathlib import Path


def attr(tag: str, name: str) -> str:
    match = re.search(
        rf'\b{re.escape(name)}\s*=\s*"([^"]*)"',
        tag,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return html.unescape(match.group(1)) if match else ""


def extract_image(source: Path, target: Path) -> None:
    content = source.read_text(encoding="utf-8", errors="ignore")

    dmd_type = re.search(r"<DMDType\b[^>]*>", content, flags=re.I | re.S)
    if not dmd_type or attr(dmd_type.group(0), "Value") != "3":
        raise RuntimeError("B2S sans FullDMD DMDType=3")

    dmd_image = re.search(r"<DMDImage\b[^>]*>", content, flags=re.I | re.S)
    if not dmd_image:
        raise RuntimeError("DMDImage absent")

    encoded = re.sub(r"\s+", "", attr(dmd_image.group(0), "Value"))
    if not encoded:
        raise RuntimeError("DMDImage sans données intégrées")

    try:
        data = base64.b64decode(encoded, validate=False)
    except Exception as exc:
        raise RuntimeError(f"DMDImage base64 invalide : {exc}") from exc

    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("DMDImage extraite mais PNG invalide")

    target.write_bytes(data)


def decode_png(path: Path):
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG invalide")

    pos = 8
    width = height = bit_depth = color_type = interlace = None
    palette = None
    transparency = None
    idat = bytearray()

    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        name = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length

        if name == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif name == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif name == b"tRNS":
            transparency = bytes(chunk)
        elif name == b"IDAT":
            idat.extend(chunk)
        elif name == b"IEND":
            break

    if not width or not height or bit_depth != 8 or interlace != 0:
        raise ValueError("PNG non compatible avec l'analyse intégrée")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if not channels:
        raise ValueError("Couleurs PNG non supportées")

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    if len(raw) < (stride + 1) * height:
        raise ValueError("PNG incomplet")

    pixels = bytearray(stride * height)
    previous = bytearray(stride)
    src = 0
    dst = 0

    for _ in range(height):
        filt = raw[src]
        src += 1
        current = bytearray(raw[src:src + stride])
        src += stride

        for i in range(stride):
            left = current[i - channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0

            if filt == 1:
                current[i] = (current[i] + left) & 0xFF
            elif filt == 2:
                current[i] = (current[i] + up) & 0xFF
            elif filt == 3:
                current[i] = (current[i] + ((left + up) // 2)) & 0xFF
            elif filt == 4:
                predictor = left + up - upper_left
                pa = abs(predictor - left)
                pb = abs(predictor - up)
                pc = abs(predictor - upper_left)
                value = left if pa <= pb and pa <= pc else (up if pb <= pc else upper_left)
                current[i] = (current[i] + value) & 0xFF
            elif filt != 0:
                raise ValueError("Filtre PNG non supporté")

        pixels[dst:dst + stride] = current
        dst += stride
        previous = current

    return width, height, color_type, channels, palette, transparency, pixels


def pixel(decoded, x: int, y: int):
    width, _, kind, channels, palette, transparency, pixels = decoded
    offset = (y * width + x) * channels

    if kind == 6:
        return tuple(pixels[offset:offset + 4])
    if kind == 2:
        red, green, blue = pixels[offset:offset + 3]
        return red, green, blue, 255
    if kind == 3:
        index = pixels[offset]
        if not palette or index >= len(palette):
            return 255, 255, 255, 255
        red, green, blue = palette[index]
        alpha = transparency[index] if transparency and index < len(transparency) else 255
        return red, green, blue, alpha
    if kind == 0:
        value = pixels[offset]
        return value, value, value, 255
    if kind == 4:
        value, alpha = pixels[offset:offset + 2]
        return value, value, value, alpha
    return 255, 255, 255, 255


def detect_frame(image: Path):
    decoded = decode_png(image)
    image_w, image_h = decoded[0], decoded[1]

    # Échantillonnage : assez détaillé pour le cadre DMD, léger pour VPX.
    step = max(1, math.ceil(max(image_w / 960, image_h / 600)))
    sample_w = math.ceil(image_w / step)
    sample_h = math.ceil(image_h / step)
    black = []

    for sy in range(sample_h):
        y = min(image_h - 1, sy * step + step // 2)
        row = bytearray(sample_w)
        for sx in range(sample_w):
            x = min(image_w - 1, sx * step + step // 2)
            red, green, blue, alpha = pixel(decoded, x, y)
            if alpha >= 150 and max(red, green, blue) <= 34:
                row[sx] = 1
        black.append(row)

    heights = [0] * sample_w
    best = None
    best_score = -1.0
    image_area = image_w * image_h

    for y, row in enumerate(black):
        for x in range(sample_w):
            heights[x] = heights[x] + 1 if row[x] else 0

        stack = []
        for x in range(sample_w + 1):
            current = heights[x] if x < sample_w else 0
            start = x

            while stack and stack[-1][1] > current:
                left, rect_h = stack.pop()
                rect_w = x - left
                start = left
                if rect_w <= 0 or rect_h <= 0:
                    continue

                px = left * step
                py = (y - rect_h + 1) * step
                pw = min(image_w - px, rect_w * step)
                ph = min(image_h - py, rect_h * step)

                if pw < image_w * 0.14 or ph < image_h * 0.035:
                    continue

                ratio = pw / ph
                area = pw * ph
                if not 2.0 <= ratio <= 7.5 or area < image_area * 0.006:
                    continue

                # Évite de prendre un fond noir plein écran comme un DMD.
                edge_touch = px <= step or py <= step or px + pw >= image_w - step or py + ph >= image_h - step
                if edge_touch and area > image_area * 0.60:
                    continue

                ratio_score = max(0.20, 1.0 - abs(math.log(ratio / 4.0)) / 1.35)
                score = area * ratio_score
                if score > best_score:
                    best_score = score
                    best = (px, py, pw, ph)

            stack.append((start, current))

    return image_w, image_h, best


def write_metadata(target: Path, image_w: int, image_h: int, frame):
    lines = [
        "# Généré automatiquement par PinCabOS.",
        f"PINCABOS_DMD_FRAME_FOUND={1 if frame else 0}",
        f"PINCABOS_DMD_FRAME_IMG_W={image_w}",
        f"PINCABOS_DMD_FRAME_IMG_H={image_h}",
    ]
    if frame:
        x, y, w, h = frame
        lines.extend((
            f"PINCABOS_DMD_FRAME_X={x}",
            f"PINCABOS_DMD_FRAME_Y={y}",
            f"PINCABOS_DMD_FRAME_W={w}",
            f"PINCABOS_DMD_FRAME_H={h}",
        ))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: source.directb2s image.png frame.env", file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    output_png = Path(sys.argv[2])
    output_env = Path(sys.argv[3])
    extract_image(source, output_png)

    try:
        image_w, image_h, frame = detect_frame(output_png)
    except Exception:
        image_w, image_h, frame = 0, 0, None

    write_metadata(output_env, image_w, image_h, frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
