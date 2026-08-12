#!/usr/bin/env bash
set -Eeuo pipefail

clear
echo "==============================================================="
echo " PINCABOS — DIRECTB2S MEDIA EXTRACTOR"
echo " Extrait images .directb2s -> media/bg.png + media/dmd.png"
echo "==============================================================="

TABLE_ROOT="/home/pinball/Tables"
MEDIA_DIR_NAME="medias"
DRY_RUN=0

usage() {
  cat <<EOF
Usage:
  media.sh [options]

Options:
  --root PATH          Racine des tables. Défaut: /home/pinball/Tables
  --media-name NAME    Nom du dossier medias. Défaut: medias
  --dry-run            Analyse seulement, ne copie rien
  -h, --help           Aide

Sorties:
  <table>/medias/bg.png
  <table>/medias/dmd.png
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      TABLE_ROOT="${2:-}"
      shift 2
      ;;
    --media-name)
      MEDIA_DIR_NAME="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERREUR: option inconnue: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "$TABLE_ROOT" ]]; then
  echo "ERREUR: racine tables introuvable: $TABLE_ROOT"
  exit 1
fi

export TABLE_ROOT MEDIA_DIR_NAME DRY_RUN

python3 - <<'PY'
from pathlib import Path
import base64
import binascii
import hashlib
import html
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

TABLE_ROOT = Path(os.environ.get("TABLE_ROOT", "/home/pinball/Tables"))
MEDIA_DIR_NAME = os.environ.get("MEDIA_DIR_NAME", "media")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

def image_type(data: bytes):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"BM"):
        return "bmp"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    return None

def image_dims(data: bytes, typ: str):
    try:
        if typ == "png" and len(data) >= 24:
            return struct.unpack(">II", data[16:24])
        if typ == "gif" and len(data) >= 10:
            return struct.unpack("<HH", data[6:10])
        if typ == "bmp" and len(data) >= 26:
            w = struct.unpack("<i", data[18:22])[0]
            h = abs(struct.unpack("<i", data[22:26])[0])
            return max(0, w), max(0, h)
        if typ == "jpg":
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                i += 2
                if marker in (0xD8, 0xD9):
                    continue
                if i + 2 > len(data):
                    break
                seglen = struct.unpack(">H", data[i:i+2])[0]
                if marker in range(0xC0, 0xC4) and i + 7 < len(data):
                    h = struct.unpack(">H", data[i+3:i+5])[0]
                    w = struct.unpack(">H", data[i+5:i+7])[0]
                    return w, h
                i += seglen
    except Exception:
        pass
    return 0, 0

def try_decode_image(value: str):
    if not value:
        return None

    value = html.unescape(value.strip())

    if "base64," in value[:120].lower():
        value = value.split(",", 1)[1]

    clean = re.sub(r"\s+", "", value)

    if len(clean) < 900:
        return None

    if not re.fullmatch(r"[A-Za-z0-9+/=]+", clean):
        return None

    pad = (-len(clean)) % 4
    if pad:
        clean += "=" * pad

    try:
        data = base64.b64decode(clean, validate=False)
    except (binascii.Error, ValueError):
        return None

    typ = image_type(data)
    if not typ:
        return None

    w, h = image_dims(data, typ)
    return {
        "data": data,
        "type": typ,
        "width": w,
        "height": h,
        "area": int(w) * int(h),
    }

def add_candidate(candidates, seen, decoded, meta):
    if not decoded:
        return

    digest = hashlib.sha256(decoded["data"]).hexdigest()
    if digest in seen:
        return

    seen.add(digest)
    decoded["sha256"] = digest
    decoded["meta"] = " ".join(str(x) for x in meta if x).strip()
    candidates.append(decoded)

def extract_candidates(b2s_path: Path):
    raw = b2s_path.read_bytes()
    text = raw.decode("utf-8", errors="ignore")

    candidates = []
    seen = set()

    # 1) XML quand possible.
    try:
        root = ET.fromstring(text)
        for elem in root.iter():
            meta_parts = [elem.tag]
            for k, v in elem.attrib.items():
                if len(str(v)) < 300:
                    meta_parts.append(f"{k}={v}")

            for k, v in elem.attrib.items():
                decoded = try_decode_image(str(v))
                add_candidate(candidates, seen, decoded, meta_parts + [k])

            if elem.text:
                decoded = try_decode_image(elem.text)
                add_candidate(candidates, seen, decoded, meta_parts + ["text"])
    except Exception:
        pass

    # 2) Fallback attributs XML/texte.
    for m in re.finditer(r'([A-Za-z0-9_:\-]+)\s*=\s*"([^"]{900,})"', text, re.S):
        key = m.group(1)
        val = m.group(2)
        around = text[max(0, m.start() - 350):m.start() + 120]
        decoded = try_decode_image(val)
        add_candidate(candidates, seen, decoded, [key, around])

    # 3) Fallback contenu entre balises.
    for m in re.finditer(r">([A-Za-z0-9+/\s=\r\n]{900,})<", text, re.S):
        val = m.group(1)
        around = text[max(0, m.start() - 250):m.start() + 80]
        decoded = try_decode_image(val)
        add_candidate(candidates, seen, decoded, [around])

    return candidates

def bg_score(c):
    meta = c.get("meta", "").lower()
    score = c.get("area", 0) / 100000.0

    for kw in ("backglass", "background", "back glass", "screen"):
        if kw in meta:
            score += 100

    for kw in ("dmd", "fulldmd", "full dmd", "grill", "score"):
        if kw in meta:
            score -= 70

    for kw in ("light", "bulb", "led", "illumination", "snippet"):
        if kw in meta:
            score -= 25

    return score

def dmd_score(c):
    meta = c.get("meta", "").lower()
    score = c.get("area", 0) / 150000.0

    for kw in ("fulldmd", "full dmd", "dmd", "score", "display", "grill"):
        if kw in meta:
            score += 120

    for kw in ("backglass", "background"):
        if kw in meta:
            score -= 80

    for kw in ("light", "bulb", "led", "illumination", "snippet"):
        if kw in meta:
            score -= 25

    return score

def select_images(candidates):
    if not candidates:
        return None, None

    sorted_by_area = sorted(
        candidates,
        key=lambda c: (c.get("area", 0), len(c.get("data", b""))),
        reverse=True,
    )

    bg = max(candidates, key=bg_score)

    remaining = [c for c in candidates if c["sha256"] != bg["sha256"]]
    if not remaining:
        return bg, None

    keyword_dmd = [
        c for c in remaining
        if re.search(r"fulldmd|full dmd|\bdmd\b|score|display|grill", c.get("meta", ""), re.I)
    ]

    if keyword_dmd:
        dmd = max(keyword_dmd, key=dmd_score)
        return bg, dmd

    # Fallback: deuxième plus grande image.
    dmd = sorted(
        remaining,
        key=lambda c: (c.get("area", 0), len(c.get("data", b""))),
        reverse=True,
    )[0]

    if dmd.get("area", 0) < 60000:
        return bg, None

    return bg, dmd

def write_png(candidate, target: Path):
    typ = candidate["type"]
    data = candidate["data"]

    if DRY_RUN:
        return

    target.parent.mkdir(parents=True, exist_ok=True)

    if typ == "png":
        target.write_bytes(data)
        return

    with tempfile.TemporaryDirectory(prefix="pincabos-b2s-img-") as td:
        src = Path(td) / f"source.{typ}"
        src.write_bytes(data)

        # 1) Pillow si disponible.
        try:
            from PIL import Image
            with Image.open(src) as im:
                im.convert("RGBA").save(target, "PNG")
            return
        except Exception:
            pass

        # 2) ImageMagick.
        magick = shutil.which("magick")
        convert = shutil.which("convert")

        if magick:
            subprocess.run([magick, str(src), str(target)], check=True)
            return

        if convert:
            subprocess.run([convert, str(src), str(target)], check=True)
            return

        raise RuntimeError(
            f"Impossible de convertir {typ} vers PNG. Installe python3-pil ou imagemagick."
        )

def fmt_img(c):
    if not c:
        return "aucune"
    return f"{c['type']} {c.get('width',0)}x{c.get('height',0)} area={c.get('area',0)}"

def process_b2s(b2s_path: Path):
    table_dir = b2s_path.parent
    media_dir = table_dir / MEDIA_DIR_NAME

    candidates = extract_candidates(b2s_path)
    bg, dmd = select_images(candidates)

    print()
    print("---------------------------------------------------------------")
    print(f"TABLE : {table_dir.name}")
    print(f"B2S   : {b2s_path.name}")
    print(f"IMG   : {len(candidates)} image(s) détectée(s)")
    print(f"BG    : {fmt_img(bg)}")
    print(f"DMD   : {fmt_img(dmd)}")
    print(f"MEDIA : {media_dir}")

    if not bg:
        print("WARN  : aucune image backglass exploitable.")
        return False, False

    bg_target = media_dir / "bg.png"
    dmd_target = media_dir / "dmd.png"

    try:
        write_png(bg, bg_target)
        if DRY_RUN:
            print(f"DRY   : écrirait {bg_target}")
        else:
            print(f"OK    : écrit {bg_target}")

        if dmd:
            write_png(dmd, dmd_target)
            if DRY_RUN:
                print(f"DRY   : écrirait {dmd_target}")
            else:
                print(f"OK    : écrit {dmd_target}")
        else:
            print("WARN  : aucune image FullDMD/DMD trouvée, dmd.png non modifié.")

        if not DRY_RUN:
            try:
                subprocess.run(["chown", "-R", "pinball:pinball", str(media_dir)], check=False)
                subprocess.run(["chmod", "-R", "u+rwX,g+rX", str(media_dir)], check=False)
            except Exception:
                pass

        return True, bool(dmd)

    except Exception as e:
        print(f"ERREUR: {e}")
        return False, False

def main():
    b2s_files = sorted(TABLE_ROOT.rglob("*.directb2s"))

    if not b2s_files:
        print(f"Aucun .directb2s trouvé dans {TABLE_ROOT}")
        return 1

    # Si plusieurs .directb2s dans le même dossier, on prend le plus gros.
    by_table = {}
    for p in b2s_files:
        by_table.setdefault(p.parent, []).append(p)

    selected = []
    for table_dir, files in sorted(by_table.items(), key=lambda x: str(x[0]).lower()):
        files = sorted(files, key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
        selected.append(files[0])
        if len(files) > 1:
            print(f"INFO: plusieurs .directb2s dans {table_dir.name}, utilisé: {files[0].name}")

    print(f"Racine tables : {TABLE_ROOT}")
    print(f"Dossier media : {MEDIA_DIR_NAME}")
    print(f"Mode          : {'DRY-RUN' if DRY_RUN else 'ÉCRITURE / ÉCRASEMENT'}")
    print(f"Tables B2S    : {len(selected)}")

    ok_bg = 0
    ok_dmd = 0

    for b2s in selected:
        bg_written, dmd_written = process_b2s(b2s)
        ok_bg += 1 if bg_written else 0
        ok_dmd += 1 if dmd_written else 0

    print()
    print("===============================================================")
    print(" RÉSUMÉ")
    print("===============================================================")
    print(f"Tables traitées       : {len(selected)}")
    print(f"bg.png générés        : {ok_bg}")
    print(f"dmd.png générés       : {ok_dmd}")
    print(f"Mode                  : {'DRY-RUN' if DRY_RUN else 'ÉCRASEMENT ACTIF'}")
    print("===============================================================")

    return 0

raise SystemExit(main())
PY
