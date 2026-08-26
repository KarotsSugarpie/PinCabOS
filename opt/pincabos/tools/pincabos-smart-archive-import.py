#!/usr/bin/env python3
# PinCabOS-File created by Karots Sugarpie
import argparse
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

try:
    import olefile
except Exception:
    olefile = None

def pincabos_force_standard_table_name(name):
    """
    Force le format:
    Table Name (Manufacturer Year)

    Exemples:
    The Leprechaun King_Original_2019_ -> The Leprechaun King (Original 2019)
    Ramones _Original 2021_           -> Ramones (Original 2021)
    Ramones_Original_2021_            -> Ramones (Original 2021)
    """
    name = str(name or "").strip()

    name = name.replace("\\", " ").replace("/", " ")
    name = re.sub(r'[:"*?<>|]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    # Cas: Table_Manufacturer_Year_
    m = re.match(r"^(?P<table>.+?)_(?P<mfg>[^_()]+)_(?P<year>\d{4})_$", name)
    if m:
        table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
        mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
        year = m.group("year").strip()
        return f"{table} ({mfg} {year})"

    # Cas: Table _Manufacturer Year_
    m = re.match(r"^(?P<table>.+?)\s+_(?P<mfg>[^_()]+?)\s+(?P<year>\d{4})_$", name)
    if m:
        table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
        mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
        year = m.group("year").strip()
        return f"{table} ({mfg} {year})"

    # Cas: Table Manufacturer 2021, seulement si pas déjà avec parenthèses
    if "(" not in name and ")" not in name:
        m = re.match(r"^(?P<table>.+?)\s+(?P<mfg>Original|Williams|Stern|Bally|Gottlieb|Data East|Sega|HauntFreaks|MOD)\s+(?P<year>\d{4})$", name, re.I)
        if m:
            table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
            mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
            year = m.group("year").strip()
            return f"{table} ({mfg} {year})"

    return name or "Imported Table"


BASE = Path("/opt/pincabos")
TABLES_ROOT = Path("/home/pinball/Tables")
IMPORT_LOGS_ROOT = BASE / "imports" / "logs"

ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".pincabos"}

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".apng"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac"}
FONT_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
DOC_EXTS = {".txt", ".pdf", ".doc", ".docx", ".rtf", ".nfo", ".md"}

MEDIA_EXTS = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS

ROOT_EXTS = {
    ".vpx",
    ".directb2s",
    ".vbs",
    ".scv",
    ".pov",
    ".res",
}

VNI_EXTS = {".pal", ".vni"}
SERUM_EXTS = {".crz", ".serum"}
ALTCOLOR_MISC_EXTS = {".pac"}

PINMAME_CFG_EXTS = {".cfg"}
PINMAME_NVRAM_EXTS = {".nv", ".nvram"}

TEMP_NAMES = {
    "extract",
    "tmp",
    "temp",
    "_raw_files",
    "raw_files",
    "upload",
    "uploads",
    "archive",
    "nested",
}

def log(msg):
    print(msg, flush=True)


def standard_table_folder_name(name):
    return pincabos_force_standard_table_name(name)



def safe_name(value):
    value = str(value or "").strip()
    value = value.replace("\\", " ").replace("/", " ")
    value = re.sub(r'[:"*?<>|]+', " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "Imported Table"

def is_temp_name(name):
    n = str(name or "").strip().lower()
    return (
        n in TEMP_NAMES
        or n.startswith("_archive_")
        or n.startswith("archive_")
        or n.startswith("_nested_")
        or n.startswith("nested_")
        or n.startswith("_forced_")
        or n.startswith("forced_")
        or n.startswith("_already_extracted_")
        or n.startswith("already_extracted_")
        or n.startswith("pincabos-")
    )

def run(cmd, timeout=1800):
    log("$ " + " ".join(str(x) for x in cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)

def list_files(root):
    return [p for p in Path(root).rglob("*") if p.is_file()]

def list_dirs(root):
    return [p for p in Path(root).rglob("*") if p.is_dir()]

def archive_probe(src):
    try:
        r = run(["7z", "l", "-slt", str(src)], timeout=180)
        return (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception as e:
        return str(e)

def archive_is_passworded(src):
    """
    Détection informative seulement.

    Une mention générale de chiffrement dans le catalogue
    ne permet pas de conclure qu'un mot de passe est requis.
    L'extraction réelle demeure la source de vérité.
    """
    data = archive_probe(src).lower()

    return any(marker in data for marker in (
        "wrong password",
        "password is incorrect",
        "can not open encrypted archive",
    ))

def archive_file_list(src):
    data = archive_probe(src)
    out = []
    for line in data.splitlines():
        line = line.strip()
        if line.startswith("Path = "):
            val = line.split("=", 1)[1].strip()
            if val and val != str(src):
                out.append(val)
    return out

def archive_kind(src):
    src = Path(src)
    if src.suffix.lower() not in ARCHIVE_EXTS:
        return ""

    files = [x.lower().replace("\\", "/") for x in archive_file_list(src)]
    names = [Path(x).name.lower() for x in files]

    if any(x.endswith(".vpx") for x in files):
        return "table_archive"

    if "pinupplayer.ini" in names or any(x.endswith(".pup") for x in files):
        return "pup_archive"

    if "altsound.ini" in names or "altsound.csv" in names or any("/altsound/" in x or x.startswith("altsound/") for x in files):
        return "altsound_archive"

    audio_files = [x for x in files if x.endswith((".mp3", ".wav", ".ogg", ".flac"))]
    if audio_files:
        if any("/music/" in x or x.startswith("music/") for x in files):
            return "music_archive"
        if len(audio_files) >= 1:
            return "music_archive"

    if any(x.endswith(".crz") for x in files):
        return "serum_archive"

    if any(x.endswith(".pal") or x.endswith(".vni") for x in files):
        return "vni_archive"

    if src.suffix.lower() == ".zip":
        # Une ROM PinMAME est souvent un ZIP avec des fichiers binaires sans VPX/media/config.
        if not any(x.endswith((
            ".vpx", ".directb2s", ".vbs", ".scv", ".pov", ".res",
            ".pup", ".mp4", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".apng",
            ".ini", ".cfg", ".nv", ".nvram", ".pal", ".vni", ".crz"
        )) for x in files):
            return "rom_zip"

    return "support_archive"

def extract_archive(src, dest):
    """
    Extrait une archive portable PinCabOS.

    Les archives RAR utilisent UnRAR officiel afin de prendre
    en charge les méthodes RAR 7 que 7-Zip peut cataloguer sans
    être capable de les décompresser.

    Les autres formats continuent d'utiliser 7-Zip.
    """
    src = Path(src)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() == ".rar":
        unrar = Path("/usr/local/bin/pincabos-unrar")

        if not unrar.is_file():
            raise RuntimeError(
                "SUPPORT RAR 7 ABSENT: "
                "/usr/local/bin/pincabos-unrar"
            )

        command = [
            str(unrar),
            "x",
            "-o+",
            "-p-",
            str(src),
            str(dest) + "/",
        ]

        extractor_name = "UnRAR"

    else:
        command = [
            "7z",
            "x",
            "-y",
            f"-o{dest}",
            str(src),
        ]

        extractor_name = "7-Zip"

    r = run(command)

    stdout = r.stdout or ""
    stderr = r.stderr or ""
    data = (stdout + "\n" + stderr).lower()

    password_errors = (
        "wrong password",
        "password is incorrect",
        "incorrect password",
        "missing password",
        "password required",
        "can not open encrypted archive",
        "cannot open encrypted archive",
    )

    if (
        r.returncode != 0
        and any(marker in data for marker in password_errors)
    ):
        raise RuntimeError(
            f"ARCHIVE PASSWORD REFUSÉE: {src}\n"
            f"Extracteur: {extractor_name}\n"
            f"{stdout}\n{stderr}"
        )

    if r.returncode != 0:
        raise RuntimeError(
            "ÉCHEC EXTRACTION ARCHIVE "
            f"(extracteur={extractor_name}, "
            f"code={r.returncode}): {src}\n"
            f"{stdout}\n{stderr}"
        )

    extracted_files = [
        item
        for item in dest.rglob("*")
        if item.is_file()
    ]

    if not extracted_files:
        raise RuntimeError(
            f"Extraction vide: {src}"
        )

    log(
        f"Extraction réussie avec {extractor_name}: "
        f"{src.name} -> {len(extracted_files)} fichier(s)"
    )

def is_password_protected_error(exc):
    return "ARCHIVE PASSWORD REFUSÉE:" in str(exc)

def copy_file(src, dest_dir, new_name=None):
    # PINCABOS_COPY_FILE_ATOMIC_V2
    #
    # Ne jamais faire copy2() directement sur un fichier existant
    # potentiellement possédé par root.
    #
    # copy2() copie d'abord vers un inode temporaire appartenant
    # à l'utilisateur courant, puis Path.replace() remplace
    # atomiquement la destination.
    #
    # Cela conserve les métadonnées copy2() sans appeler utime()
    # sur l'ancien inode root-owned.

    src = Path(src)
    dest_dir = Path(dest_dir)

    dest_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    dest = (
        dest_dir
        / safe_name(
            new_name or src.name
        )
    )

    with tempfile.NamedTemporaryFile(
        prefix=f".{dest.name}.pincabos-copy-",
        suffix=".tmp",
        dir=str(dest_dir),
        delete=False,
    ) as handle:
        temporary = Path(handle.name)

    try:
        shutil.copy2(
            src,
            temporary,
        )
        temporary.replace(
            dest
        )
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

    log(
        f"INSTALLÉ: {src} -> {dest}"
    )
    return dest

def copy_dir_contents(src_dir, dest_dir):
    src_dir = Path(src_dir)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(src_dir)
        target = dest_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        copied.append(str(target))
        log(f"INSTALLÉ: {f} -> {target}")

    return copied

def extract_all_inputs(batch_dir, extract_root):
    batch_dir = Path(batch_dir)
    extract_root = Path(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)

    raw_dir = extract_root / "_raw_files"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for item in sorted(batch_dir.rglob("*")):
        if not item.is_file():
            continue

        suffix = item.suffix.lower()

        if suffix in ARCHIVE_EXTS:
            kind = archive_kind(item)

            if kind == "rom_zip":
                copy_file(item, raw_dir)
                continue

            dest = extract_root / ("archive_" + safe_name(item.stem))
            log("")
            log("==================================================")
            log(f"ARCHIVE: {item}")
            log(f"TYPE: {kind}")
            log("==================================================")
            try:
                extract_archive(item, dest)
            except RuntimeError as exc:
                # Une table chiffrée est bloquante. Les composants annexes
                # (AltSound, PuP, médias, VNI, etc.) sont ignorés proprement.
                if is_password_protected_error(exc) and kind != "table_archive":
                    log(f"WARNING: ARCHIVE OPTIONNEL IGNORÉ — protégé par mot de passe: {item} | type={kind}")
                    continue
                raise
        else:
            copy_file(item, raw_dir)

    changed = True
    loop = 0

    while changed and loop < 6:
        changed = False
        loop += 1

        for item in sorted(extract_root.rglob("*")):
            if not item.is_file():
                continue

            if item.suffix.lower() not in ARCHIVE_EXTS:
                continue

            if item.name.startswith("already_extracted_"):
                continue

            kind = archive_kind(item)

            if kind == "rom_zip":
                continue

            dest = item.parent / ("nested_" + safe_name(item.stem))
            if dest.exists():
                continue

            log("")
            log(f"ARCHIVE INTERNE: {item}")
            log(f"TYPE INTERNE: {kind}")
            try:
                extract_archive(item, dest)
            except RuntimeError as exc:
                if is_password_protected_error(exc) and kind != "table_archive":
                    log(f"WARNING: ARCHIVE INTERNE OPTIONNEL IGNORÉ — protégé par mot de passe: {item} | type={kind}")
                    item.rename(item.with_name("already_extracted_" + item.name))
                    changed = True
                    continue
                raise

            item.rename(item.with_name("already_extracted_" + item.name))
            changed = True

def choose_main_vpx(root):
    vpxs = [p for p in list_files(root) if p.suffix.lower() == ".vpx"]
    if not vpxs:
        return None
    vpxs.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    return vpxs[0]

def read_text_script(path):
    path = Path(path)
    for enc in ("utf-8-sig", "utf-16", "utf-16-le", "latin-1"):
        try:
            data = path.read_text(encoding=enc, errors="ignore")
            if data.strip():
                return data
        except Exception:
            pass
    return ""


def extract_vbs_from_vpx(vpx_path, dest_dir=None):
    # PINCABOS_VBS_VPINFE_SOURCE_V1
    # VPinFE est la première vérité pour le chemin VPX.
    import os
    import re
    import shlex
    import shutil
    import subprocess

    vpx_path = Path(vpx_path)
    if not vpx_path.is_file() or vpx_path.suffix.lower() != ".vpx":
        return None

    dest_dir = Path(dest_dir) if dest_dir else vpx_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    expected_src_vbs = vpx_path.with_suffix(".vbs")
    final_vbs = dest_dir / (vpx_path.stem + ".vbs")

    if final_vbs.exists() and final_vbs.stat().st_size >= 1000:
        log(f"INFO: VBS déjà présent, extraction sautée: {final_vbs}")
        return final_vbs

    candidates = []

    def add_candidate(raw):
        value = str(raw or "").strip().strip("\"'")
        if not value:
            return

        try:
            parts = shlex.split(value)
        except Exception:
            parts = [value]

        if not parts:
            return

        candidate = Path(parts[0]).expanduser()

        if candidate not in candidates:
            candidates.append(candidate)

    # PINCABOS_VPX_BINARY_DISCOVERY_V2
    # VPinFE lance un wrapper; -ExtractVBS doit utiliser le vrai ELF.
    direct_candidates = []
    home = Path("/home/pinball")

    for pattern in (
        "VPinballX_BGFX-*/VPinballX_BGFX",
        "VPinballX-*/VPinballX",
        "VPinballX*/VPinballX_BGFX",
        "VPinballX*/VPinballX",
    ):
        for candidate in home.glob(pattern):
            try:
                if (
                    candidate.is_file()
                    and candidate not in direct_candidates
                ):
                    direct_candidates.append(candidate)
            except OSError:
                pass

    try:
        direct_candidates.sort(
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        pass

    for candidate in direct_candidates:
        add_candidate(candidate)

    for discovered_ini in (
        Path("/home/pinball/.config/vpinfe/vpinfe.ini"),
        Path("/opt/pincabos/config/vpinfe/vpinfe.ini"),
        Path("/home/pinball/vpinfe/vpinfe.ini"),
    ):
        if not discovered_ini.is_file():
            continue

        ini_text = discovered_ini.read_text(
            encoding="utf-8",
            errors="replace",
        )

        for line in ini_text.splitlines():
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            normalized = re.sub(
                r"[^a-z0-9]",
                "",
                key.lower(),
            )

            if normalized in {
                "vpxbinpath",
                "vpxbinarypath",
                "vpxexecutablepath",
            }:
                add_candidate(value)

    vpinfe_ini = Path("/opt/pincabos/config/vpinfe/vpinfe.ini")
    if vpinfe_ini.is_file():
        ini_text = vpinfe_ini.read_text(
            encoding="utf-8",
            errors="replace",
        )

        for line in ini_text.splitlines():
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())

            if (
                "vpx" in normalized
                and "executable" in normalized
                and "path" in normalized
            ):
                add_candidate(value)

    launcher = Path("/opt/pincabos/scripts/VPXlauncher.sh")
    if launcher.is_file():
        launcher_text = launcher.read_text(
            encoding="utf-8",
            errors="replace",
        )

        for variable in ("VPX_MAIN", "VPX_EXECUTABLE", "VPX_BIN"):
            match = re.search(
                rf'^\s*{variable}=["\']([^"\']+)["\']',
                launcher_text,
                re.MULTILINE,
            )
            if match:
                add_candidate(match.group(1))

    for command in ("VPinballX_BGFX", "VPinballX-BGFX", "VPinballX"):
        found = shutil.which(command)
        if found:
            add_candidate(found)

    for root in (
        Path("/opt/pincabos/apps/vpinball"),
        Path("/opt/pincabos/vpinball"),
        Path("/home/pinball/vpinball"),
    ):
        if not root.is_dir():
            continue
        for pattern in ("VPinballX_BGFX", "VPinballX-BGFX", "VPinballX"):
            for candidate in root.rglob(pattern):
                add_candidate(candidate)

    valid = []
    for candidate in candidates:
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                valid.append(candidate)
        except OSError:
            pass

    if not valid:
        log("WARNING: aucun exécutable VPX valide trouvé.")
        return None

    for candidate in {expected_src_vbs, final_vbs}:
        try:
            if candidate.exists() and candidate.stat().st_size == 0:
                candidate.unlink()
        except OSError:
            pass

    runuser = shutil.which("runuser")
    attempts = []

    for vpxbin in valid:
        for switch in ("-ExtractVBS", "-extractvbs"):
            direct = [str(vpxbin), switch, str(vpx_path)]

            if os.geteuid() == 0:
                if not runuser:
                    continue

                cmd = [
                    runuser,
                    "-u",
                    "pinball",
                    "--",
                    "/usr/bin/env",
                    "HOME=/home/pinball",
                    "USER=pinball",
                    "LOGNAME=pinball",
                    "DISPLAY=:0",
                    "XAUTHORITY=/home/pinball/.Xauthority",
                    "XDG_RUNTIME_DIR=/run/user/1000",
                    "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus",
                ] + direct
                env = None
            else:
                cmd = direct
                env = os.environ.copy()
                env.update(
                    {
                        "HOME": "/home/pinball",
                        "USER": "pinball",
                        "LOGNAME": "pinball",
                        "DISPLAY": ":0",
                        "XAUTHORITY": "/home/pinball/.Xauthority",
                        "XDG_RUNTIME_DIR": "/run/user/1000",
                        "DBUS_SESSION_BUS_ADDRESS": (
                            "unix:path=/run/user/1000/bus"
                        ),
                    }
                )

            log("$ " + " ".join(cmd))

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(vpxbin.parent),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=180,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                attempts.append(f"{vpxbin.name} {switch}: timeout")
                continue
            except Exception as exc:
                attempts.append(f"{vpxbin.name} {switch}: {exc}")
                continue

            output = proc.stdout or ""
            for line in output.splitlines()[-80:]:
                log("extractvbs: " + line)

            attempts.append(
                f"{vpxbin.name} {switch}: rc={proc.returncode}"
            )

            extracted = None
            for candidate_vbs in (
                expected_src_vbs,
                vpx_path.parent / (vpx_path.stem + ".vbs"),
                Path.cwd() / (vpx_path.stem + ".vbs"),
            ):
                try:
                    if (
                        candidate_vbs.is_file()
                        and candidate_vbs.stat().st_size >= 1000
                    ):
                        extracted = candidate_vbs
                        break
                except OSError:
                    pass

            if extracted is None:
                continue

            if extracted.resolve() != final_vbs.resolve():
                shutil.copy2(extracted, final_vbs)

            if final_vbs.is_file() and final_vbs.stat().st_size >= 1000:
                log(
                    "VBS EXTRAIT OFFICIEL: "
                    f"{vpx_path} -> {final_vbs} "
                    f"({final_vbs.stat().st_size} bytes)"
                )
                return final_vbs

    log(
        "WARNING: extraction VBS impossible après essais: "
        + " | ".join(attempts[-20:])
    )
    return None



def detect_rom_from_script_text(script):
    script = str(script or "")

    # Détection robuste sans regex complexe:
    # cherche GameName, RomName, cGameName ou OptRom puis extrait la valeur entre quotes.
    keys = ("cGameName", "GameName", "RomName", "OptRom")

    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("'"):
            continue

        low = line.lower()

        for key in keys:
            k = key.lower()
            if k not in low:
                continue
            if "=" not in line:
                continue

            right = line.split("=", 1)[1].strip()

            # Enlever commentaires VBScript après la valeur si possible.
            if "'" in right:
                right = right.split("'", 1)[0].strip()

            if len(right) >= 2 and right[0] in ("'", '"'):
                quote = right[0]
                rest = right[1:]
                if quote in rest:
                    rom = rest.split(quote, 1)[0].strip()
                else:
                    rom = rest.strip()
            else:
                rom = right.split()[0].strip() if right.split() else ""

            rom = rom.strip().strip('"').strip("'").strip()

            if rom:
                return rom[:-4] if rom.lower().endswith(".zip") else rom

    return ""

def detect_rom_name(root, provided_rom="", main_vpx=None):
    provided_rom = str(provided_rom or "").strip()
    if provided_rom:
        return provided_rom[:-4] if provided_rom.lower().endswith(".zip") else provided_rom

    for vbs in sorted([p for p in list_files(root) if p.suffix.lower() == ".vbs"], key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True):
        rom = detect_rom_from_script_text(read_text_script(vbs))
        if rom:
            log(f"ROM détectée depuis VBS: {rom} ({vbs})")
            return rom

    if main_vpx:
        tmp_vbs = extract_vbs_from_vpx(main_vpx, Path(root) / "_raw_files")
        if tmp_vbs:
            rom = detect_rom_from_script_text(read_text_script(tmp_vbs))
            if rom:
                log(f"ROM détectée depuis VPX/VBS extrait: {rom}")
                return rom

    roms = []
    for p in list_files(root):
        if p.suffix.lower() == ".zip" and archive_kind(p) == "rom_zip":
            roms.append(p)
    if roms:
        roms.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
        return roms[0].stem
    return ""



# PINCABOS_PUP_ROM_FIRST_V1
def safe_pup_pack_folder_name(value):
    """
    Conserve le nom exact demandé par le script PuP, mais refuse
    tout élément qui pourrait sortir de pupvideos/.
    """
    name = str(value or "").strip()

    if not name:
        return ""

    if name in {".", ".."} or "\x00" in name:
        log(f"WARNING: nom PuP invalide refusé: {name!r}")
        return ""

    if "/" in name or "\\" in name:
        log(f"WARNING: nom PuP avec séparateur refusé: {name!r}")
        return ""

    return name


def detect_pup_name_from_script_text(script):
    """
    Détecte le nom du dossier PuP demandé par le script VPX.

    Priorité :
      1. Nom littéral dans PuPlayer.B2SInit.
      2. pGameName / PuPGameName / PUPPackName.
      3. pGameName = cGameName / GameName / RomName.

    Un nom n'est accepté que si le script utilise réellement PuP.
    """
    import re

    script = str(script or "")
    low_script = script.lower()

    has_pup = (
        "pinupplayer.pindisplay" in low_script
        or "puplayer.b2sinit" in low_script
        or "puplayer.b2sdata" in low_script
        or "pupinit" in low_script
    )

    if not has_pup:
        return ""

    direct = re.search(
        r'(?im)\bPuPlayer\.B2SInit\s+""\s*,\s*"([^"]+)"',
        script,
    )

    if direct:
        return safe_pup_pack_folder_name(direct.group(1))

    keys = ("pGameName", "PuPGameName", "PUPPackName")

    for raw_line in script.splitlines():
        line = raw_line.strip()

        if not line or line.startswith("'"):
            continue

        code = line.split("'", 1)[0].strip()

        for key in keys:
            pattern = (
                r'(?i)\b'
                + re.escape(key)
                + r'\b\s*=\s*"([^"]+)"'
            )

            match = re.search(pattern, code)

            if match:
                name = safe_pup_pack_folder_name(match.group(1))
                if name:
                    return name

    # Cas fréquent : pGameName = cGameName.
    for raw_line in script.splitlines():
        line = raw_line.strip()

        if not line or line.startswith("'"):
            continue

        code = line.split("'", 1)[0].strip()

        match = re.search(
            r'(?i)\bpGameName\b\s*=\s*'
            r'(cGameName|GameName|RomName|OptRom)\b',
            code,
        )

        if match:
            return safe_pup_pack_folder_name(
                detect_rom_from_script_text(script)
            )

    return ""


def read_table_script_for_identity(root, main_vpx=None):
    """
    Lit d'abord un VBS fourni. À défaut, extrait temporairement le script
    de la table principale sans contaminer l'arbre d'import.
    """
    import tempfile

    root = Path(root)
    candidates = []
    seen = set()

    def add_candidate(path):
        path = Path(path)

        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)

        if key in seen or not path.is_file():
            return

        seen.add(key)
        candidates.append(path)

    if main_vpx:
        main_vpx = Path(main_vpx)
        add_candidate(main_vpx.with_suffix(".vbs"))

        for candidate in sorted(
            root.rglob(main_vpx.stem + ".vbs"),
            key=lambda item: item.stat().st_size if item.exists() else 0,
            reverse=True,
        ):
            add_candidate(candidate)

    for candidate in sorted(
        [p for p in root.rglob("*.vbs") if p.is_file()],
        key=lambda item: item.stat().st_size if item.exists() else 0,
        reverse=True,
    ):
        add_candidate(candidate)

    for candidate in candidates:
        script = read_text_script(candidate)

        if script:
            return script, candidate

    if main_vpx:
        with tempfile.TemporaryDirectory(
            prefix="pincabos-identity-vbs-"
        ) as temp_dir:
            extracted = extract_vbs_from_vpx(
                main_vpx,
                Path(temp_dir),
            )

            if extracted:
                script = read_text_script(extracted)

                if script:
                    return script, Path(extracted)

    return "", None


def detect_import_identity(root, provided_rom="", main_vpx=None):
    """
    Première analyse Smart Import :
    ROM et PuP sont déterminés avant toute installation/copie.
    """
    provided_rom = str(provided_rom or "").strip()
    script, script_path = read_table_script_for_identity(root, main_vpx)

    script_rom = detect_rom_from_script_text(script) if script else ""
    pup_pack = detect_pup_name_from_script_text(script) if script else ""

    if provided_rom:
        rom = (
            provided_rom[:-4]
            if provided_rom.lower().endswith(".zip")
            else provided_rom
        )

        if script_rom and script_rom.lower() != rom.lower():
            log(
                "WARNING: ROM fournie manuellement différente du script: "
                f"manuel={rom} script={script_rom}"
            )
    else:
        rom = script_rom or detect_rom_name(
            root,
            "",
            main_vpx=main_vpx,
        )

    if script_path:
        log(f"Analyse script         : {script_path}")
    else:
        log("WARNING: aucun script lisible pour analyse ROM/PuP.")

    log(f"ROM pré-analysée        : {rom or '(aucune)'}")

    if pup_pack:
        log(
            "PuP-Pack pré-analysé   : "
            f"{pup_pack} -> pupvideos/{pup_pack}/"
        )
    elif script:
        log(
            "WARNING: script sans nom PuP explicite; "
            "aucun dossier PuP ne sera inventé."
        )

    return {
        "rom": rom,
        "pup_pack": pup_pack,
        "script_path": str(script_path) if script_path else "",
    }


def ensure_table_tree(table_dir):
    """
    Structure portable officielle PinCabOS, autonome par table.

    Aucun contenu PinMAME/AltSound/AltColor n'est installé globalement.
    """
    table_dir = Path(table_dir)

    for rel in (
        "pinmame/roms",
        "pinmame/altcolor",
        "pinmame/altsound",
        "pinmame/ini",
        "pinmame/cfg",
        "pinmame/nvram",
        "pupvideos",
        "music",
        "ultradmd",
        "fonts",
        "medias",
        "extras",
    ):
        (table_dir / rel).mkdir(parents=True, exist_ok=True)

    return table_dir

def normalize_media_name(src):
    p = Path(src)
    name = p.name.lower()
    suffix = p.suffix.lower()

    if "wheel" in name:
        return "wheel" + suffix

    if "backglass" in name or "background" in name or name.startswith("bg") or "(backglass)" in name:
        return "bg" + suffix

    if "realdmd" in name or "real-dmd" in name or "(realdmd)" in name:
        return "realdmd" + suffix

    if "fulldmd" in name or "dmd" in name or "(dmd)" in name:
        return "dmd" + suffix

    if "flyer" in name:
        return "flyer" + suffix

    if "cab" in name or "cabinet" in name:
        return "cab" + suffix

    if "playfield" in name or "(playfield)" in name:
        if suffix in VIDEO_EXTS:
            return "table" + suffix
        if suffix in IMAGE_EXTS:
            return "table" + suffix

    if suffix in AUDIO_EXTS and ("audio" in name or "music" in name or "theme" in name):
        return "audio" + suffix

    return p.name


def find_literal_pupvideos_dirs(root):
    """
    Règle PinCabOS:
    Si l'archive contient un dossier nommé pupvideos / PupVideos,
    on copie son contenu tel quel dans <table>/pupvideos/.
    On ne renomme pas, on ne classe pas, on ne touche pas à ce qu'il y a dedans.
    """
    root = Path(root)
    found = []

    for d in sorted(root.rglob("*")):
        if not d.is_dir():
            continue

        if d.name.lower() != "pupvideos":
            continue

        # Ne jamais prendre un dossier temporaire créé par l'importeur comme racine logique.
        if any(is_temp_name(part) for part in d.parts):
            # On permet quand même archive_xxx/.../pupvideos, car archive_xxx est notre extract container.
            # Le dossier important est le dossier pupvideos lui-même.
            pass

        found.append(d)

    # Garder seulement les pupvideos les plus hauts.
    final = []
    for d in found:
        if any(parent in found for parent in d.parents):
            continue
        final.append(d)

    return final


def looks_like_pup_dir(d):
    """
    Reconnaît uniquement la vraie racine d'un PupPack.

    Important : ne pas utiliser une recherche récursive ici, sinon le
    dossier parent d'une archive peut être pris pour le PupPack et toute
    la table risque d'être copiée dans pupvideos/.
    """
    d = Path(d)

    if is_temp_name(d.name) or not d.is_dir():
        return False

    direct_files = [p for p in d.iterdir() if p.is_file()]
    direct_dirs = {p.name.lower() for p in d.iterdir() if p.is_dir()}
    names = {p.name.lower() for p in direct_files}
    lname = d.name.lower()

    if "pinupplayer.ini" in names or "screens.pup" in names:
        return True

    if any(p.suffix.lower() == ".pup" for p in direct_files):
        return True

    pup_asset_dirs = {"fonts", "pupalphas", "pupoverlays"}
    if "pup" in lname and direct_dirs.intersection(pup_asset_dirs):
        return True

    return False


def looks_like_music_dir(d):
    d = Path(d)
    if is_temp_name(d.name):
        return False

    lname = d.name.lower()
    files = list_files(d)
    audio_count = sum(1 for x in files if x.suffix.lower() in AUDIO_EXTS)

    if lname == "music":
        return audio_count >= 1

    return False


def looks_like_altsound_dir(d):
    d = Path(d)
    if is_temp_name(d.name):
        return False

    files = list_files(d)
    names = {x.name.lower() for x in files}

    if "altsound.ini" in names or "altsound.csv" in names:
        return True

    audio_count = sum(1 for x in files if x.suffix.lower() in AUDIO_EXTS)
    return audio_count >= 10 and "alt" in d.name.lower()

def looks_like_ultradmd_dir(d):
    d = Path(d)
    if is_temp_name(d.name):
        return False

    lname = d.name.lower()
    files = list_files(d)
    names = {x.name.lower() for x in files}

    if lname.endswith(".ultradmd"):
        return True

    if "ultradmd" in lname or "flexdmd" in lname:
        return True

    if any("ultradmd" in n or "flexdmd" in n for n in names):
        return True

    return False

def find_roots(root, predicate):
    candidates = []

    for d in sorted(list_dirs(root)):
        if predicate(d):
            candidates.append(d)

    final = []
    for d in candidates:
        if any(parent in candidates for parent in d.parents):
            continue
        final.append(d)

    return final

def best_plugin_folder_name(d, fallback):
    d = Path(d)
    n = safe_name(d.name)
    if n and not is_temp_name(n) and n.lower() not in {"pupvideos", "pupvideo", "puppack", "pup-pack", "altsound"}:
        return n
    return safe_name(fallback)

def detect_ultradmd_folder_name(ultra_roots, table_title):
    for d in ultra_roots:
        n = safe_name(d.name)
        if is_temp_name(n):
            continue
        if n.lower().endswith(".ultradmd"):
            return n
        if "ultradmd" in n.lower() or "flexdmd" in n.lower():
            return n
    return safe_name(table_title) + ".UltraDMD"

def should_skip_file(f):
    text = str(f).lower()
    return "/already_extracted_" in text


def classify_and_install(extract_root, table_dir, rom, pup_pack=""):
    # PINCABOS_PORTABLE_LAYOUT_V2
    #
    # Une table est entièrement autonome :
    #
    #   <Table>/
    #     <Table>.vpx
    #     <Table>.directb2s
    #     fonts/
    #     pinmame/
    #       roms/
    #       altcolor/<ROM>/
    #       altsound/<ROM>/
    #
    # Aucun dossier racine altsound/, serum/, vni/ ou altcolor/ n'est utilisé.

    extract_root = Path(extract_root)
    table_dir = Path(table_dir)
    ensure_table_tree(table_dir)

    table_title = safe_name(table_dir.name)
    rom_name = safe_name(rom or table_title)

    pup_pack_name = safe_pup_pack_folder_name(pup_pack)
    pup_target = table_dir / "pupvideos"

    if pup_pack_name:
        pup_target = pup_target / pup_pack_name
        log(
            "PuP destination script  : "
            f"{pup_target}"
        )
    else:
        log(
            "WARNING: PuP sans nom détecté; "
            "conservation dans pupvideos/ sans sous-dossier inventé."
        )

    installed = {
        "root": [],
        "fonts": [],
        "pupvideos": [],
        "music": [],
        "altsound": [],
        "ultradmd": [],
        "pinmame_roms": [],
        "pinmame_altcolor": [],
        "pinmame_ini": [],
        "pinmame_cfg": [],
        "pinmame_nvram": [],
        "pinmame_alias": [],
        "medias": [],
        "extras": [],
    }

    copied = set()

    def put(category, source, destination, new_name=None):
        source = Path(source)
        destination = Path(destination)

        try:
            source_key = str(source.resolve())
        except Exception:
            source_key = str(source)

        final_name = str(new_name or source.name)
        key = (source_key, str(destination), final_name)

        if key in copied:
            return None

        copied.add(key)
        result = copy_file(source, destination, final_name)
        installed[category].append(str(result))
        return result

    def copy_tree(category, source_dir, destination_dir, fonts_to_table=True):
        source_dir = Path(source_dir)
        destination_dir = Path(destination_dir)

        for item in sorted(source_dir.rglob("*")):
            if not item.is_file():
                continue

            suffix = item.suffix.lower()

            # Les fonts doivent toujours rester directement dans <table>/fonts/.
            if fonts_to_table and suffix in FONT_EXTS:
                put("fonts", item, table_dir / "fonts", item.name)
                continue

            relative = item.relative_to(source_dir)
            put(category, item, destination_dir / relative.parent, relative.name)

    excluded_dirs = set()

    # 1) PuP : vraie racine avant un sous-dossier PupVideos.
    # PINCABOS_PUP_ROOT_FIRST_V1
    true_pup_roots = []

    for candidate in find_roots(extract_root, looks_like_pup_dir):
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate

        if resolved not in true_pup_roots:
            true_pup_roots.append(resolved)

    highest_pup_roots = []
    for candidate in true_pup_roots:
        if any(
            other != candidate and other in candidate.parents
            for other in true_pup_roots
        ):
            continue
        highest_pup_roots.append(candidate)

    def pup_root_score(candidate):
        score = 0
        name = candidate.name.casefold()

        if pup_pack_name and name == pup_pack_name.casefold():
            score += 1000000

        direct_names = {
            item.name.casefold()
            for item in candidate.iterdir()
            if item.is_file()
        }

        if "screens.pup" in direct_names:
            score += 500000
        if "playlists.pup" in direct_names:
            score += 100000
        if "triggers.pup" in direct_names:
            score += 50000

        try:
            score += min(
                sum(
                    1
                    for item in candidate.rglob("*")
                    if item.is_file()
                ),
                40000,
            )
        except Exception:
            pass

        return score

    if highest_pup_roots:
        highest_pup_roots.sort(
            key=pup_root_score,
            reverse=True,
        )
        pup_source = highest_pup_roots[0]
        destination_name = (
            pup_pack_name
            or best_plugin_folder_name(pup_source, table_title)
        )
        destination = (
            table_dir
            / "pupvideos"
            / safe_pup_pack_folder_name(destination_name)
        )

        log(
            "PuP vraie racine       : "
            f"{pup_source} -> {destination}"
        )

        copy_tree(
            "pupvideos",
            pup_source,
            destination,
            fonts_to_table=False,
        )

        for font in sorted(pup_source.rglob("*")):
            if font.is_file() and font.suffix.lower() in FONT_EXTS:
                put("fonts", font, table_dir / "fonts", font.name)

        excluded_dirs.add(pup_source.resolve())

        for ignored in highest_pup_roots[1:]:
            log(
                "WARNING: autre racine PuP ignorée pour éviter "
                f"un mélange de packs: {ignored}"
            )
            excluded_dirs.add(ignored.resolve())
    else:
        literal_pupvideos_dirs = find_literal_pupvideos_dirs(
            extract_root
        )

        for wrapper in literal_pupvideos_dirs:
            source = wrapper
            destination = table_dir / "pupvideos"

            if pup_pack_name:
                matches = [
                    child
                    for child in wrapper.iterdir()
                    if (
                        child.is_dir()
                        and child.name.casefold()
                        == pup_pack_name.casefold()
                    )
                ]

                if len(matches) == 1:
                    source = matches[0]

                destination = (
                    table_dir
                    / "pupvideos"
                    / pup_pack_name
                )

            copy_tree(
                "pupvideos",
                source,
                destination,
                fonts_to_table=False,
            )
            excluded_dirs.add(wrapper.resolve())

    # 3) Musique par table.
    for music_dir in find_roots(extract_root, looks_like_music_dir):
        resolved = music_dir.resolve()
        if any(root == resolved or root in resolved.parents for root in excluded_dirs):
            continue
        copy_tree("music", music_dir, table_dir / "music")
        excluded_dirs.add(resolved)

    # 4) AltSound exclusivement dans pinmame/altsound/<ROM>/.
    altsound_target = table_dir / "pinmame" / "altsound" / rom_name
    for altsound_dir in find_roots(extract_root, looks_like_altsound_dir):
        resolved = altsound_dir.resolve()
        if any(root == resolved or root in resolved.parents for root in excluded_dirs):
            continue
        copy_tree("altsound", altsound_dir, altsound_target)
        excluded_dirs.add(resolved)

    # 5) UltraDMD par table.
    ultra_roots = find_roots(extract_root, looks_like_ultradmd_dir)
    ultra_name = detect_ultradmd_folder_name(ultra_roots, table_title)
    for ultra in ultra_roots:
        resolved = ultra.resolve()
        if any(root == resolved or root in resolved.parents for root in excluded_dirs):
            continue
        copy_tree("ultradmd", ultra, table_dir / "ultradmd" / ultra_name)
        excluded_dirs.add(resolved)

    all_files = sorted(list_files(extract_root))

    # Le VPX et le B2S principal sont toujours renommés selon le titre final.
    vpx_files = [f for f in all_files if f.suffix.lower() == ".vpx"]
    vpx_files.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)

    if vpx_files:
        put("root", vpx_files[0], table_dir, f"{table_title}.vpx")

    b2s_files = [f for f in all_files if f.suffix.lower() == ".directb2s"]
    b2s_files.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)

    if b2s_files:
        put("root", b2s_files[0], table_dir, f"{table_title}.directb2s")

    vpx_stems = {f.stem.lower() for f in vpx_files}
    if vpx_files:
        vpx_stems.add(table_title.lower())

    for f in all_files:
        if not f.is_file() or should_skip_file(f):
            continue

        suffix = f.suffix.lower()

        # Font = toujours <table>/fonts/, même si elle provient d'un dossier PUP.
        if suffix in FONT_EXTS:
            put("fonts", f, table_dir / "fonts", f.name)
            continue

        try:
            parent_resolved = f.parent.resolve()
        except Exception:
            parent_resolved = f.parent

        if any(root == parent_resolved or root in parent_resolved.parents for root in excluded_dirs):
            continue

        # Déjà traité comme table/B2S principal.
        if suffix == ".vpx" or suffix == ".directb2s":
            continue

        path_parts = {part.lower() for part in f.parts}
        filename_lower = f.name.lower()

        # AltSound identifié même lorsqu'il est livré sans archive dédiée.
        if (
            "altsound" in path_parts
            or filename_lower in {"altsound.ini", "altsound.csv"}
        ):
            put("altsound", f, altsound_target, f.name)
            continue

        # Toutes les variantes AltColor/Serum vont au même endroit autonome.
        if suffix in (VNI_EXTS | SERUM_EXTS | ALTCOLOR_MISC_EXTS):
            put(
                "pinmame_altcolor",
                f,
                table_dir / "pinmame" / "altcolor" / rom_name,
                f.name,
            )
            continue

        # ROM PinMAME.
        if suffix == ".zip" and archive_kind(f) == "rom_zip":
            put("pinmame_roms", f, table_dir / "pinmame" / "roms", f.name)
            continue

        # VBS associé à la table.
        if suffix == ".vbs":
            put("root", f, table_dir, f"{table_title}.vbs")
            continue

        # Fichiers VPX associés.
        if suffix in {".scv", ".pov", ".res"}:
            put("root", f, table_dir, f.name)
            continue

        # Configurations PinMAME.
        if suffix == ".ini":
            if f.stem.lower() in vpx_stems:
                put("root", f, table_dir, f.name)
            elif rom and f.stem.lower().startswith(str(rom).lower()):
                put("pinmame_ini", f, table_dir / "pinmame" / "ini", f.name)
            else:
                put("extras", f, table_dir / "extras", f.name)
            continue

        if suffix in PINMAME_CFG_EXTS:
            put("pinmame_cfg", f, table_dir / "pinmame" / "cfg", f.name)
            continue

        if suffix in PINMAME_NVRAM_EXTS:
            put("pinmame_nvram", f, table_dir / "pinmame" / "nvram", f.name)
            continue

        if suffix in {".dat", ".txt"} and rom and f.stem.lower().startswith(str(rom).lower()):
            put("pinmame_alias", f, table_dir / "pinmame", f.name)
            continue

        # Médias restant : PUP, UltraDMD, musique ou médias généraux.
        if suffix in AUDIO_EXTS:
            put("music", f, table_dir / "music", f.name)
            continue

        if suffix in VIDEO_EXTS or suffix in IMAGE_EXTS:
            if "pup" in path_parts or "pinup" in path_parts:
                put("pupvideos", f, pup_target, f.name)
            elif "ultradmd" in path_parts:
                put("ultradmd", f, table_dir / "ultradmd" / ultra_name, f.name)
            else:
                put("medias", f, table_dir / "medias", normalize_media_name(f))
            continue

        # Archives non reconnues et documents : extras par table.
        put("extras", f, table_dir / "extras", f.name)

    return installed

def write_info_and_manifest(table_dir, title, manufacturer, year, rom, vpsid, ipdbid, installed):
    # PINCABOS_MANIFEST_RELATIVE_PATHS_V1
    table_dir = Path(table_dir)
    table_resolved = table_dir.resolve()
    normalized_installed = {}

    for category, values in installed.items():
        clean_values = []
        seen_values = set()

        for value in values:
            candidate = Path(str(value))

            try:
                if candidate.is_absolute():
                    relative = candidate.resolve().relative_to(
                        table_resolved
                    )
                else:
                    relative = candidate
            except Exception:
                continue

            portable = relative.as_posix().lstrip("/")

            if portable and portable not in seen_values:
                seen_values.add(portable)
                clean_values.append(portable)

        normalized_installed[category] = clean_values

    installed = normalized_installed
    info = {
        "Info": {
            "Title": title,
            "Manufacturer": manufacturer,
            "Year": str(year or ""),
            "Rom": rom,
            "VPSId": vpsid,
            "IPDBId": ipdbid,
        }
    }

    info_path = table_dir / f"{safe_name(title)}.info"
    info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "format": "PinCabOS portable VPX table",
        "format_version": 6,
        "model": "single-folder-portable-table",
        "title": title,
        "manufacturer": manufacturer,
        "year": str(year or ""),
        "rom": rom,
        "vpsid": vpsid,
        "ipdbid": ipdbid,
        "table_dir": str(table_dir),
        "layout": {
            "root": [
                "*.vpx",
                "*.directb2s",
                "*.info",
                "*.ini",
                "*.vbs",
                "*.scv",
                "*.pov",
                "*.res"
            ],
            "altsound": "pinmame/altsound/<name>/",
            "cache": "cache/",
            "medias": "medias/",
            "music": "music/",
            "pinmame": {
                "roms": "pinmame/roms/",
                "nvram": "pinmame/nvram/",
                "cfg": "pinmame/cfg/",
                "ini": "pinmame/ini/",
                "alias": "pinmame/alias.txt"
            },
            "pupvideos": "pupvideos/",
            "scripts": "scripts/",
            "serum": "pinmame/altcolor/<name>/",
            "ultradmd": "<Table Name>.UltraDMD/",
            "user": "user/",
            "vni": "pinmame/altcolor/<name>/",
            "extras": "extras/"
        },
        "legacy_global_paths_used": False,
        "installed": installed,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    manifest_path = table_dir / "pincabos-table-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    log(f"META: {info_path}")
    log(f"META: {manifest_path}")


def write_import_tree_log(table_dir, title, rom, installed):
    IMPORT_LOGS_ROOT.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_name = safe_name(title).replace(" ", "_")
    log_path = IMPORT_LOGS_ROOT / f"import-{stamp}-{log_name}.txt"

    try:
        tree = subprocess.run(
            ["find", str(table_dir), "-maxdepth", "8", "-print"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        tree_output = tree.stdout.strip()
        tree_error = tree.stderr.strip()
    except Exception as e:
        tree_output = ""
        tree_error = str(e)

    lines = []
    lines.append("======================================================================")
    lines.append(" PinCabOS - Import table log")
    lines.append("======================================================================")
    lines.append(f"Date       : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Title      : {title}")
    lines.append(f"ROM        : {rom or '(aucune)'}")
    lines.append(f"Table dir  : {table_dir}")
    lines.append("")
    lines.append("======================================================================")
    lines.append(" Résumé install")
    lines.append("======================================================================")
    for k, v in installed.items():
        lines.append(f"{k}: {len(v)}")
    lines.append("")
    lines.append("======================================================================")
    lines.append(" Fichiers installés par catégorie")
    lines.append("======================================================================")
    for k, v in installed.items():
        lines.append("")
        lines.append(f"--- {k} ({len(v)}) ---")
        for item in v:
            lines.append(str(item))
    lines.append("")
    lines.append("======================================================================")
    lines.append(" Résultat find")
    lines.append("======================================================================")
    lines.append(tree_output)
    if tree_error:
        lines.append("")
        lines.append("======================================================================")
        lines.append(" Erreurs find")
        lines.append("======================================================================")
        lines.append(tree_error)
    lines.append("")
    lines.append("======================================================================")
    lines.append(" FIN")
    lines.append("======================================================================")

    log_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")

    try:
        subprocess.run(["chown", "pinball:pinball", str(log_path)], timeout=10, check=False)
        subprocess.run(["chmod", "664", str(log_path)], timeout=10, check=False)
    except Exception:
        pass

    log(f"IMPORT LOG: {log_path}")
    return log_path



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch_dir")
    ap.add_argument("--title", default="")
    ap.add_argument("--manufacturer", default="")
    ap.add_argument("--year", default="")
    ap.add_argument("--vpsid", default="")
    ap.add_argument("--rom", default="")
    ap.add_argument("--ipdbid", default="")
    args = ap.parse_args()

    batch_dir = Path(args.batch_dir)
    if not batch_dir.exists():
        raise SystemExit(f"Batch introuvable: {batch_dir}")

    title = standard_table_folder_name(safe_name(args.title or batch_dir.name))
    manufacturer = args.manufacturer.strip()
    year = str(args.year or "").strip()
    vpsid = args.vpsid.strip()
    ipdbid = args.ipdbid.strip()

    TABLES_ROOT.mkdir(parents=True, exist_ok=True)

    log("==================================================")
    log(" PinCabOS Import - Portable VPX table complete")
    log("==================================================")
    log(f"Batch       : {batch_dir}")
    log(f"Tables root : {TABLES_ROOT}")
    log(f"Title       : {title}")

    with tempfile.TemporaryDirectory(prefix="pincabos-portable-table-import-") as td:
        extract_root = Path(td) / "extract"
        extract_all_inputs(batch_dir, extract_root)

        main_vpx = choose_main_vpx(extract_root)
        if not main_vpx:
            raise SystemExit("ERREUR: aucun fichier .vpx trouvé après extraction. Import refusé.")

        # Analyse AVANT toute copie : ROM + nom exact du PuP-Pack.
        identity = detect_import_identity(
            extract_root,
            args.rom,
            main_vpx=main_vpx,
        )
        rom = identity["rom"]
        pup_pack = identity["pup_pack"]

        # PINCABOS_PUP_ALIAS_ROM_TRUTH_V1
        if pup_pack:
            bundled_roms = [
                item
                for item in list_files(extract_root)
                if (
                    item.suffix.lower() == ".zip"
                    and archive_kind(item) == "rom_zip"
                )
            ]

            if not bundled_roms:
                if str(rom or "").casefold() != str(pup_pack).casefold():
                    log(
                        "ROM corrigée par alias PuP : "
                        f"{rom or '(vide)'} -> {pup_pack}"
                    )
                rom = pup_pack


        table_dir = TABLES_ROOT / title
        ensure_table_tree(table_dir)

        # PinCabOS portable: toujours créer le .vbs final à côté du .vpx.
        # Utilise VPinballX-BGFX -extractvbs et refuse les VBS vides.
        final_vbs = extract_vbs_from_vpx(main_vpx, table_dir)
        if final_vbs:
            log(f"VBS final extrait      : {final_vbs}")
        else:
            log("WARNING: VBS final non extrait. La table peut quand même fonctionner via script embarqué, mais l'import portable sera moins complet.")

        log("")
        log("==================================================")
        log(" Installation portable VPX")
        log("==================================================")
        log(f"VPX principal détecté : {main_vpx}")
        log(f"ROM détectée          : {rom or '(aucune)'}")
        log(
            "PuP-Pack détecté       : "
            f"{pup_pack or '(aucun / non explicite)'}"
        )
        log(f"Table dir             : {table_dir}")

        installed = classify_and_install(extract_root, table_dir, rom, pup_pack=pup_pack)

    write_info_and_manifest(table_dir, title, manufacturer, year, rom, vpsid, ipdbid, installed)

    import_log_path = write_import_tree_log(table_dir, title, rom, installed)

    try:
        subprocess.run(["chown", "-R", "pinball:pinball", str(table_dir)], timeout=60, check=False)
        subprocess.run(["chmod", "-R", "u+rwX,g+rwX,o+rX", str(table_dir)], timeout=60, check=False)
    except Exception:
        pass

    log("")
    log("==================================================")
    log(" Résumé")
    log("==================================================")
    for k, v in installed.items():
        log(f"{k}: {len(v)}")

    log("")
    log("=== Résultat table ===")
    subprocess.run(["find", str(table_dir), "-maxdepth", "5", "-print"], check=False)

    log("")
    log(f"LOG TXT: {import_log_path}")

    # PINCABOS_TABLE_TREE_IMPORT_TARGETED_V5
    #
    # Une importation réussie ne doit normaliser que
    # la table qui vient d'être créée.
    #
    # Ne jamais rescanner toute la bibliothèque ici.
    try:
        tree_result = subprocess.run(
            [
                "/opt/pincabos/tools/pincabos-table-tree.sh",
                "--apply",
                "--quiet",
                f"--table={table_dir}",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if tree_result.returncode != 0:
            detail = (
                (tree_result.stdout or "")
                + "\n"
                + (tree_result.stderr or "")
            ).strip()

            log(
                "WARNING: normalisation ciblée table-tree "
                f"retour={tree_result.returncode}"
            )

            if detail:
                log(detail)
        else:
            log(
                "Table-tree ciblé       : "
                f"{table_dir}"
            )
    except Exception as exc:
        log(
            "WARNING: normalisation ciblée "
            f"table-tree impossible: {exc}"
        )

    log("IMPORT OK - modèle portable VPX complet")
    return 0


# PINCABOS_FULLDMD_SMART_IMPORT_HOOK_V4
# Ajouté par l'installateur V4 après audit de la garde __main__ et du marqueur portable V2.
# Le hook est volontairement différé à la fin du processus : il ne traite que les B2S
# FullDMD modifiés pendant l'import. Il ne modifie aucun fichier de table source.
def _pincabos_fulldmd_after_smart_import() -> None:
    try:
        import atexit
        import os
        import subprocess
        from pathlib import Path

        def _run() -> None:
            dispatcher = Path('/opt/pincabos/bin/pincabos-fulldmd-process-table.py')
            if not dispatcher.is_file():
                return
            subprocess.Popen(
                [str(dispatcher), '--recent-minutes', '20'],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        atexit.register(_run)
    except Exception:
        pass

_pincabos_fulldmd_after_smart_import()
# PINCABOS_FULLDMD_SMART_IMPORT_HOOK_V4_END


# PINCABOS_TABLE_TREE_IMPORT_TARGETED_V5_ENTRYPOINT
if __name__ == "__main__":
    raise SystemExit(main())
