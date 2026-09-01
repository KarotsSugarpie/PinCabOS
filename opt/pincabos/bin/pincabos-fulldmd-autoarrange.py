#!/usr/bin/env python3
"""PinCabOS FullDMD AutoArrange V1.

Analyse une image PNG FullDMD et sauvegarde un rectangle DMD par table.
Aucune dépendance externe : PNG 8-bit non entrelacé (B2S standard).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path


# PINCABOS_FULLDMD_SAFE_MARGIN_V3
DEFAULT_SAFE_MARGIN_PX = 5


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    except FileNotFoundError:
        pass
    return values


def x11_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    for candidate in ("/run/lightdm/root/:0", "/var/run/lightdm/root/:0", "/home/pinball/.Xauthority"):
        if Path(candidate).is_file():
            probe = env.copy()
            probe["XAUTHORITY"] = candidate
            result = subprocess.run(
                ["xdpyinfo"], env=probe, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3
            )
            if result.returncode == 0:
                return probe
    return env


def target_geometry() -> tuple[int, int, int, int, str]:
    """Ecran du role fulldmd. Ordre : geometrie publiee par la topologie
    (display-aliases.env, derivee de screens.json), puis xrandr sur la sortie
    du role. Aucun repli code en dur : mieux vaut echouer clairement que
    d'ecrire un rectangle calibre pour l'ecran d'une autre machine."""
    aliases = parse_env(Path("/opt/pincabos/config/display-aliases.env"))
    output = aliases.get("PINCABOS_FULLDMD_OUTPUT", "")
    if aliases.get("PINCABOS_FULLDMD_AVAILABLE") == "1":
        match = re.match(
            r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$",
            aliases.get("PINCABOS_FULLDMD_GEOMETRY", ""),
        )
        if match:
            width, height, x, y = map(int, match.groups())
            return x, y, width, height, output or "fulldmd"
    if output:
        try:
            data = subprocess.check_output(
                ["xrandr", "--query"], text=True, errors="replace", env=x11_env(), timeout=5
            )
            pattern = re.compile(
                rf"^{re.escape(output)}\s+connected(?:\s+primary)?\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)",
                re.MULTILINE,
            )
            match = pattern.search(data)
            if match:
                width, height, x, y = map(int, match.groups())
                return x, y, width, height, output
        except Exception:
            pass
    raise SystemExit(
        "fulldmd introuvable : ni display-aliases.env (role fulldmd), ni xrandr. "
        "Verifier la configuration des ecrans (page Ecrans de la WebApp)."
    )


def decode_png(path: Path) -> tuple[int, int, bytearray]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG invalide")
    pos = 8
    width = height = bit_depth = color_type = interlace = None
    palette: list[tuple[int, int, int]] | None = None
    transparency: bytes | None = None
    idat = bytearray()
    while pos + 12 <= len(data):
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        name = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + size]
        if len(chunk) != size:
            raise ValueError("PNG tronqué")
        pos += 12 + size
        if name == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
        elif name == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif name == b"tRNS":
            transparency = bytes(chunk)
        elif name == b"IDAT":
            idat.extend(chunk)
        elif name == b"IEND":
            break
    if not width or not height or bit_depth != 8 or interlace != 0:
        raise ValueError("PNG non supporté : 8-bit non entrelacé requis")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError("Couleurs PNG non supportées")
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    expected = (stride + 1) * height
    if len(raw) < expected:
        raise ValueError("PNG incomplet")
    native = bytearray(stride * height)
    prior = bytearray(stride)
    source = 0
    dest = 0
    for _ in range(height):
        filt = raw[source]
        source += 1
        current = bytearray(raw[source:source + stride])
        source += stride
        for i in range(stride):
            left = current[i - channels] if i >= channels else 0
            up = prior[i]
            upper_left = prior[i - channels] if i >= channels else 0
            if filt == 1:
                current[i] = (current[i] + left) & 0xFF
            elif filt == 2:
                current[i] = (current[i] + up) & 0xFF
            elif filt == 3:
                current[i] = (current[i] + ((left + up) >> 1)) & 0xFF
            elif filt == 4:
                p = left + up - upper_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - upper_left)
                predictor = left if pa <= pb and pa <= pc else (up if pb <= pc else upper_left)
                current[i] = (current[i] + predictor) & 0xFF
            elif filt != 0:
                raise ValueError(f"Filtre PNG invalide : {filt}")
        native[dest:dest + stride] = current
        prior = current
        dest += stride

    rgba = bytearray(width * height * 4)
    out = 0
    src = 0
    if color_type == 6:
        for _ in range(width * height):
            rgba[out:out + 4] = native[src:src + 4]
            src += 4
            out += 4
    elif color_type == 2:
        for _ in range(width * height):
            rgba[out:out + 3] = native[src:src + 3]
            rgba[out + 3] = 255
            src += 3
            out += 4
    elif color_type == 0:
        for _ in range(width * height):
            v = native[src]
            rgba[out:out + 3] = bytes((v, v, v))
            rgba[out + 3] = 255
            src += 1
            out += 4
    elif color_type == 4:
        for _ in range(width * height):
            v, a = native[src], native[src + 1]
            rgba[out:out + 3] = bytes((v, v, v))
            rgba[out + 3] = a
            src += 2
            out += 4
    else:  # indexed
        if palette is None:
            raise ValueError("Palette PNG manquante")
        for _ in range(width * height):
            index = native[src]
            src += 1
            if index >= len(palette):
                raise ValueError("Index palette invalide")
            r, g, b = palette[index]
            rgba[out:out + 3] = bytes((r, g, b))
            rgba[out + 3] = transparency[index] if transparency and index < len(transparency) else 255
            out += 4
    return width, height, rgba


def is_dark(rgba: bytearray, pixel: int, threshold: int = 26) -> bool:
    pos = pixel * 4
    if rgba[pos + 3] < 180:
        return False
    return rgba[pos] <= threshold and rgba[pos + 1] <= threshold and rgba[pos + 2] <= threshold


def max_rectangles(
    rgba: bytearray,
    image_w: int,
    image_h: int,
    sx: int,
    sy: int,
    sw: int,
    sh: int,
    step: int,
    global_w: int,
    global_h: int,
) -> list[tuple[float, int, int, int, int]]:
    out_w = max(1, (sw + step - 1) // step)
    heights = [0] * out_w
    candidates: list[tuple[float, int, int, int, int]] = []
    min_width = max(12, int(global_w * 0.16 / step))
    min_height = max(5, int(global_h * 0.025 / step))

    for local_y in range(0, sh, step):
        y = sy + local_y
        for col in range(out_w):
            x = sx + col * step
            heights[col] = heights[col] + 1 if is_dark(rgba, y * image_w + x) else 0

        stack: list[tuple[int, int]] = []
        for i in range(out_w + 1):
            current = heights[i] if i < out_w else 0
            start = i
            while stack and stack[-1][1] > current:
                start0, h = stack.pop()
                rw = i - start0
                if rw >= min_width and h >= min_height:
                    rx = sx + start0 * step
                    ry = sy + (local_y // step - h + 1) * step
                    rwidth = min(sw - start0 * step, rw * step)
                    rheight = min(sh - (ry - sy), h * step)
                    aspect = rwidth / max(1, rheight)
                    # On cherche une vraie fenêtre DMD, pas un bord noir de l'image.
                    if 1.70 <= aspect <= 9.50:
                        gx0, gy0 = rx, ry
                        gx1, gy1 = rx + rwidth, ry + rheight
                        touches = int(gx0 <= 1) + int(gy0 <= 1) + int(gx1 >= global_w - 1) + int(gy1 >= global_h - 1)
                        area = (rwidth * rheight) / max(1, global_w * global_h)
                        aspect_bonus = math.exp(-abs(math.log(aspect / 4.0)) * 0.72)
                        score = (math.sqrt(max(area, 0.00001)) * 100.0 * aspect_bonus) - (touches * 5.0)
                        if area >= 0.012:
                            candidates.append((score, rx, ry, rwidth, rheight))
                start = start0
            if not stack or stack[-1][1] < current:
                stack.append((start, current))
    candidates.sort(reverse=True)
    return candidates[:40]


def detect_rect(rgba: bytearray, width: int, height: int) -> tuple[tuple[int, int, int, int], float]:
    # Première passe : rapide, max 960x600.
    step = max(1, math.ceil(max(width / 960, height / 600)))
    coarse = max_rectangles(rgba, width, height, 0, 0, width, height, step, width, height)
    if not coarse:
        raise RuntimeError("Aucun rectangle noir DMD fiable trouvé")
    _, x, y, w, h = coarse[0]

    # Seconde passe : recherche au pixel dans une zone limitée autour du meilleur candidat.
    pad_x = max(24, int(w * 0.18))
    pad_y = max(16, int(h * 0.35))
    sx = max(0, x - pad_x)
    sy = max(0, y - pad_y)
    ex = min(width, x + w + pad_x)
    ey = min(height, y + h + pad_y)
    refined = max_rectangles(rgba, width, height, sx, sy, ex - sx, ey - sy, 1, width, height)
    if refined:
        score, x, y, w, h = refined[0]
    else:
        score = coarse[0][0]

    # Débarrasse un éventuel contour noir d'un pixel : c'est la zone intérieure qui doit recevoir le DMD.
    inset = 1 if w > 80 and h > 30 else 0
    x += inset
    y += inset
    w -= inset * 2
    h -= inset * 2
    if w < 32 or h < 12:
        raise RuntimeError("Rectangle détecté trop petit")
    confidence = max(1.0, min(99.0, round(score * 4.1, 1)))
    return (x, y, w, h), confidence


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--table-dir", required=True, type=Path)
    parser.add_argument("--margin", type=int, default=DEFAULT_SAFE_MARGIN_PX, help="Marge de securite cible en pixels (defaut: 5)")
    args = parser.parse_args()

    image = args.image.resolve()
    table_dir = args.table_dir.resolve()
    assets = table_dir / "fulldmd"
    if not image.is_file() or assets not in image.parents:
        raise RuntimeError("Image FullDMD invalide")
    width, height, rgba = decode_png(image)
    (source_x, source_y, source_w, source_h), confidence = detect_rect(rgba, width, height)

    target_x, target_y, target_w, target_h, output = target_geometry()
    x = target_x + round(source_x * target_w / width)
    y = target_y + round(source_y * target_h / height)
    w = max(1, round(source_w * target_w / width))
    h = max(1, round(source_h * target_h / height))
    # Limites de sécurité sur l'écran cible.
    x = max(target_x, min(x, target_x + target_w - 1))
    y = max(target_y, min(y, target_y + target_h - 1))
    w = min(w, target_x + target_w - x)
    h = min(h, target_y + target_h - y)

    # Marge de securite sur l'ecran final : le DMD reste entierement
    # a l'interieur du cadre noir meme si sa bordure est tres fine.
    margin = max(0, int(args.margin))
    max_margin = max(0, min((w - 32) // 2, (h - 12) // 2))
    margin = min(margin, max_margin)
    if margin:
        x += margin
        y += margin
        w -= margin * 2
        h -= margin * 2

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    layout = {
        "schema": "pincabos-fulldmd-layout-v1",
        "generated_at": stamp,
        "mode": "auto",
        "image": image.name,
        "source": {"width": width, "height": height},
        "target": {"output": output, "x": target_x, "y": target_y, "width": target_w, "height": target_h},
        "dmd_source": {"x": source_x, "y": source_y, "width": source_w, "height": source_h},
        "safety_margin": {"pixels": margin, "applied_to": "target"},
        "dmd": {"x": x, "y": y, "width": w, "height": h, "confidence": confidence},
    }
    atomic_write(assets / "PinCabOS-DMD-layout.json", json.dumps(layout, ensure_ascii=False, indent=2) + "\n")
    env = "\n".join([
        "# PINCABOS_FULLDMD_AUTOARRANGE_V1",
        f"# generated_at={stamp}",
        f"PINCABOS_DMD_X={x}",
        f"PINCABOS_DMD_Y={y}",
        f"PINCABOS_DMD_W={w}",
        f"PINCABOS_DMD_H={h}",
        f"PINCABOS_DMD_SOURCE_X={source_x}",
        f"PINCABOS_DMD_SOURCE_Y={source_y}",
        f"PINCABOS_DMD_SOURCE_W={source_w}",
        f"PINCABOS_DMD_SOURCE_H={source_h}",
        f"PINCABOS_DMD_CONFIDENCE={confidence}",
        f"PINCABOS_DMD_SAFE_MARGIN={margin}",
        "PINCABOS_DMD_MODE=auto",
        "",
    ])
    atomic_write(assets / "PinCabOS-DMD-layout.env", env)
    os.chown(assets / "PinCabOS-DMD-layout.json", 1000, 1000)
    os.chown(assets / "PinCabOS-DMD-layout.env", 1000, 1000)
    print(json.dumps(layout, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERREUR: {exc}", file=sys.stderr)
        raise SystemExit(1)
