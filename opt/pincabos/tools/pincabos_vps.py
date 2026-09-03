#!/usr/bin/env python3
"""pincabos_vps : identification des tables par la base Virtual Pinball
Spreadsheet (VPS) et diagnostic de ce qui manque a chacune.

PINCABOS_VPS_V1

Pourquoi : un ini patche sur un cabinet est une connaissance enfermee dans ce
cabinet. La base VPS (https://virtualpinballspreadsheet.github.io, ~2 500
tables, JSON public sur GitHub) donne a chaque table un identifiant stable et
liste ce qui existe pour elle : fichiers VPX, ROM attendues, B2S, PuP-Packs,
POV, couleurs alternatives. Sur le cab de Yohann, 28 tables sur 28 ont ete
rattachees rien qu'avec le nom du dossier « Nom (Fabricant Annee) ».

Ce module :
  - garde la base en cache local (/var/cache/pincabos/vps, rafraichie a la
    semaine par pincabos-vps-refresh.timer, ou a la demande) ;
  - rattache chaque dossier de table a son identifiant VPS et l'ecrit dans le
    manifeste deja present (pincabos-table-manifest.json, champs `vpsid` et
    `ipdbid` prevus par Karots, restes vides jusqu'ici) ;
  - produit un diagnostic par table : ROM attendue contre ROM presente, pack
    present et nomme comme la ROM, B2S, POV, couleurs alternatives.

Il n'ecrit RIEN dans les ini : identification et diagnostic seulement.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, "/opt/pincabos/tools")
try:
    from pincabos_paths import PATHS as _PATHS
    TABLES_ROOT = Path(_PATHS.tables)
except ImportError:
    TABLES_ROOT = Path("/home/pinball/Tables")

DB_URL = "https://raw.githubusercontent.com/VirtualPinballSpreadsheet/vps-db/main/db/vpsdb.json"
VPS_SITE = "https://virtualpinballspreadsheet.github.io/?game="
CACHE_DIR = Path("/var/cache/pincabos/vps")
DB_PATH = CACHE_DIR / "vpsdb.json"
META_PATH = CACHE_DIR / "vpsdb.meta.json"
MAX_AGE_DAYS = 7
MANIFEST = "pincabos-table-manifest.json"
PACK_DIRS = ("pupvideos", "pupvideo", "pinupvideos", "pinupvideo")


# --- base -------------------------------------------------------------------
def db_status(db_path: Path = DB_PATH, meta_path: Path = META_PATH) -> dict:
    out = {"present": db_path.is_file(), "path": str(db_path), "entries": 0, "age_days": None, "fetched_at": None}
    if not out["present"]:
        return out
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        out["entries"] = int(meta.get("entries", 0))
        out["fetched_at"] = meta.get("fetched_at")
    except (OSError, ValueError):
        pass
    try:
        out["age_days"] = round((time.time() - db_path.stat().st_mtime) / 86400, 1)
    except OSError:
        pass
    out["stale"] = out["age_days"] is None or out["age_days"] > MAX_AGE_DAYS
    return out


def refresh(force: bool = False, db_path: Path = DB_PATH, meta_path: Path = META_PATH, url: str = DB_URL) -> dict:
    """Telecharge la base si absente ou plus vieille que MAX_AGE_DAYS (ou force)."""
    st = db_status(db_path, meta_path)
    if st["present"] and not st["stale"] and not force:
        return {"refreshed": False, "reason": f"base a jour ({st['age_days']} j)", **st}
    db_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "PinCabOS-VPS/1"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list) or len(data) < 100:
        raise ValueError("base VPS illisible ou tronquee")
    fd, tmp = tempfile.mkstemp(prefix=".vpsdb.", dir=str(db_path.parent))
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    os.chmod(tmp, 0o664)
    os.replace(tmp, db_path)
    meta_path.write_text(json.dumps({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "entries": len(data), "url": url}), encoding="utf-8")
    return {"refreshed": True, "reason": "telechargee", **db_status(db_path, meta_path)}


_DB_CACHE: dict = {}


def load_db(db_path: Path = DB_PATH) -> list:
    key = str(db_path)
    try:
        mtime = db_path.stat().st_mtime
    except OSError:
        return []
    cached = _DB_CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    data = json.loads(db_path.read_text(encoding="utf-8"))
    _DB_CACHE[key] = (mtime, data)
    return data


# --- normalisation / rattachement ------------------------------------------
def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def parse_folder(name: str) -> tuple[str, str, str]:
    """« Terminator 2 - Judgment Day (Williams 1991) » -> (titre, fabricant, annee)."""
    m = re.match(r"^(.*?)\s*\(([^()]*?)\s*(\d{4})?\)\s*$", name.strip())
    if not m:
        return name.strip(), "", ""
    return m.group(1).strip(), (m.group(2) or "").strip(), (m.group(3) or "").strip()


def _index(db: list) -> dict:
    idx = getattr(db, "_pco_index", None) if hasattr(db, "_pco_index") else None
    key = id(db)
    cached = _DB_CACHE.get(("idx", key))
    if cached:
        return cached
    idx = {}
    for t in db:
        idx.setdefault(normalize(t.get("name", "")), []).append(t)
    _DB_CACHE[("idx", key)] = idx
    return idx


def _rom_versions(entry: dict) -> list[str]:
    return [str(r.get("version") or "").lower() for r in entry.get("romFiles") or [] if r.get("version")]


def match(db: list, title: str, manufacturer: str = "", year: str = "", rom: str | None = None) -> tuple[dict | None, list, str]:
    """(meilleure entree ou None, candidats, comment). Ordre : nom exact, puis
    nom approchant, filtres annee et fabricant, puis ROM pour departager."""
    idx = _index(db)
    n = normalize(title)
    how = []
    cands = list(idx.get(n, []))
    if cands:
        how.append("nom")
    else:
        proches = difflib.get_close_matches(n, list(idx.keys()), n=6, cutoff=0.86)
        for k in proches:
            cands.extend(idx[k])
        if cands:
            how.append("nom approchant")
    if not cands and rom:
        r = rom.lower()
        cands = [t for t in db if r in _rom_versions(t)]
        if cands:
            how.append("rom")
    if year:
        c2 = [t for t in cands if str(t.get("year")) == str(year)]
        if c2:
            cands = c2
            how.append("annee")
    if manufacturer:
        m = normalize(manufacturer).split(" ")[0]
        c3 = [t for t in cands if m and normalize(t.get("manufacturer", "")).startswith(m)]
        if c3:
            cands = c3
            how.append("fabricant")
    if len(cands) > 1 and rom:
        c4 = [t for t in cands if rom.lower() in _rom_versions(t)]
        if len(c4) == 1:
            cands = c4
            how.append("rom")
    # doublons (meme id) possibles via les noms approchants
    vus, uniques = set(), []
    for t in cands:
        if t.get("id") not in vus:
            vus.add(t.get("id"))
            uniques.append(t)
    if len(uniques) == 1:
        return uniques[0], uniques, "+".join(how)
    return None, uniques, "+".join(how) if uniques else "aucun"


def _ipdb_id(entry: dict) -> str:
    m = re.search(r"[?&]id=(\d+)", entry.get("ipdbUrl") or "")
    return m.group(1) if m else ""


def read_manifest(table_dir: Path) -> dict:
    p = Path(table_dir) / MANIFEST
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def present_roms(table_dir: Path) -> list[str]:
    d = Path(table_dir) / "pinmame" / "roms"
    try:
        return sorted(p.stem.lower() for p in d.iterdir() if p.suffix.lower() == ".zip")
    except OSError:
        return []


def table_identity(table_dir: Path) -> dict:
    table_dir = Path(table_dir)
    man = read_manifest(table_dir)
    title, manu, year = parse_folder(table_dir.name)
    rom = str(man.get("rom") or "").strip().lower()
    if not rom:
        roms = present_roms(table_dir)
        rom = roms[0] if len(roms) == 1 else ""
    return {
        "dir": str(table_dir), "folder": table_dir.name,
        "title": str(man.get("title") or title).strip() or title,
        "manufacturer": str(man.get("manufacturer") or manu).strip(),
        "year": str(man.get("year") or year).strip(),
        "rom": rom,
        "vpsid_manifest": str(man.get("vpsid") or "").strip(),
        "vps_confirmed": bool((man.get("vps") or {}).get("confirmed")),
    }


def _summary(entry: dict) -> dict:
    return {"id": entry.get("id"), "name": entry.get("name"), "manufacturer": entry.get("manufacturer"),
            "year": entry.get("year"), "ipdbid": _ipdb_id(entry), "url": VPS_SITE + str(entry.get("id"))}


def entry_by_id(db: list, vpsid: str) -> dict | None:
    for t in db:
        if t.get("id") == vpsid:
            return t
    return None


def identify(table_dir: Path, db: list) -> dict:
    """Rattachement d'un dossier : statut ok / ambigu / aucun. Un vpsid deja
    ecrit dans le manifeste (choisi a la main ou pose avant) a priorite."""
    ident = table_identity(table_dir)
    out = {**ident, "status": "aucun", "how": "", "entry": None, "candidates": []}
    if ident["vpsid_manifest"]:
        e = entry_by_id(db, ident["vpsid_manifest"])
        if e:
            out.update(status="ok", how="manifeste", entry=_summary(e))
            return out
    # le titre du manifeste peut contenir « (Fabricant Annee) » : on le nettoie
    titre, _, _ = parse_folder(ident["title"]) if "(" in ident["title"] else (ident["title"], "", "")
    best, cands, how = match(db, titre, ident["manufacturer"], ident["year"], ident["rom"] or None)
    out["candidates"] = [_summary(c) for c in cands[:8]]
    out["how"] = how
    if best:
        out.update(status="ok", entry=_summary(best))
    elif cands:
        out["status"] = "ambigu"
    return out


def apply_manifest(table_dir: Path, result: dict, force: bool = False, confirmed: bool = False) -> bool:
    """Ecrit vpsid / ipdbid dans pincabos-table-manifest.json. Sans force, un
    vpsid deja present n'est pas remplace. Retourne True si le fichier a change."""
    if result.get("status") != "ok" or not result.get("entry"):
        return False
    p = Path(table_dir) / MANIFEST
    man = read_manifest(table_dir)
    if not man:
        man = {"format": "PinCabOs portable VPX table", "title": Path(table_dir).name}
    e = result["entry"]
    if man.get("vpsid") and not force:
        return False
    nouveau = dict(man)
    nouveau["vpsid"] = e["id"]
    if e.get("ipdbid") and (force or not man.get("ipdbid")):
        nouveau["ipdbid"] = e["ipdbid"]
    nouveau["vps"] = {"name": e["name"], "manufacturer": e.get("manufacturer"), "year": e.get("year"),
                      "how": result.get("how", ""), "matched_at": time.strftime("%Y-%m-%d"), "confirmed": bool(confirmed)}
    if nouveau == man:
        return False
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(nouveau, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    return True


# --- diagnostic ---------------------------------------------------------------
def _zip_files(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as z:
            return len([n for n in z.namelist() if not n.endswith("/")])
    except (OSError, zipfile.BadZipFile):
        return -1


def _pack_root(table_dir: Path) -> Path | None:
    """Le dossier de packs, s'il contient quelque chose : le squelette d'import
    cree un `pupvideos/` VIDE sur chaque table, ce n'est pas un pack."""
    for name in PACK_DIRS:
        for child in table_dir.iterdir() if table_dir.is_dir() else []:
            if child.name.lower() == name and child.is_dir():
                try:
                    if any(child.iterdir()):
                        return child
                except OSError:
                    pass
    return None


def _file_urls(entry: dict | None, key: str) -> list[dict]:
    out = []
    for f in (entry or {}).get(key) or []:
        urls = [u.get("url") for u in f.get("urls") or [] if isinstance(u, dict) and u.get("url") and not u.get("broken")]
        out.append({"id": f.get("id"), "version": f.get("version"), "authors": f.get("authors") or [], "url": urls[0] if urls else "", "comment": f.get("comment") or ""})
    return out


def diagnostic(table_dir: Path, entry: dict | None, rom_hint: str = "") -> dict:
    table_dir = Path(table_dir)
    expected = _rom_versions(entry) if entry else []
    present = present_roms(table_dir)
    zips = {}
    for stem in present:
        zips[stem] = _zip_files(table_dir / "pinmame" / "roms" / f"{stem}.zip")
    if present and (not expected or any(p in expected for p in present)):
        rom_status = "ok"
    elif present:
        rom_status = "non referencee"
    elif expected:
        rom_status = "absente"
    else:
        rom_status = "sans rom"
    # le nombre de fichiers d'un zip ne dit pas si le jeu de ROM est complet
    # (lah_113 ou sman_261 tournent avec un seul fichier) : il est affiche,
    # jamais interprete. Seul un zip illisible est un probleme.
    rom_warn = [f"{s}.zip illisible" for s, n in zips.items() if n < 0]
    b2s = sorted(p.name for p in table_dir.glob("*.directb2s"))
    pov = sorted(p.name for p in table_dir.glob("*.pov"))
    pack_root = _pack_root(table_dir)
    packs, screens_root, alias_ok = [], False, None
    if pack_root:
        screens_root = (pack_root / "screens.pup").is_file()
        try:
            packs = sorted(c.name for c in pack_root.iterdir() if c.is_dir() and (c / "screens.pup").is_file())
        except OSError:
            packs = []
        # l'alias n'a de sens qu'avec une vraie ROM emulee (zip present) : une
        # table originale (Oz) declare un cGameName pour son pack sans ROM,
        # et le lanceur ne pose un lien qu'a partir des ROM trouvees.
        rom = (present[0] if len(present) == 1 else (rom_hint.lower() if rom_hint and rom_hint.lower() in present else "")) if present else ""
        if rom and packs:
            alias_ok = any(p.lower() == rom for p in packs)
    altcolor = False
    for d in (table_dir / "pinmame" / "altcolor", table_dir / "serum"):
        try:
            altcolor = altcolor or any(d.iterdir())
        except OSError:
            pass
    vps = entry or {}
    return {
        "rom": {"expected": expected, "present": present, "status": rom_status, "zip_files": zips, "warnings": rom_warn,
                "vps": _file_urls(entry, "romFiles")},
        "b2s": {"present": b2s, "vps_count": len(vps.get("b2sFiles") or []), "vps": _file_urls(entry, "b2sFiles")[:5]},
        "pup": {"root": str(pack_root) if pack_root else "", "packs": packs, "screens_at_root": screens_root,
                "alias_ok": alias_ok, "vps_count": len(vps.get("pupPackFiles") or []), "vps": _file_urls(entry, "pupPackFiles")[:5]},
        "pov": {"present": pov, "vps_count": len(vps.get("povFiles") or []), "vps": _file_urls(entry, "povFiles")[:5]},
        "altcolor": {"present": altcolor, "vps_count": len(vps.get("altColorFiles") or []), "vps": _file_urls(entry, "altColorFiles")[:5]},
        "original_sans_rom": not expected and not present,
        "broken": bool(vps.get("broken")),
        "vpx_versions": [f.get("version") for f in vps.get("tableFiles") or [] if f.get("version")][:8],
    }


def problemes(diag: dict) -> list[str]:
    """Phrases courtes pour la page : ce qui empeche ou gene le jeu."""
    out = []
    r = diag["rom"]
    if r["status"] == "absente":
        out.append("ROM absente : attendue " + ", ".join(r["expected"][:3]))
    elif r["status"] == "non referencee":
        out.append("ROM presente (" + ", ".join(r["present"]) + ") mais non referencee par VPS" + (" (attendue " + ", ".join(r["expected"][:2]) + ")" if r["expected"] else ""))
    out.extend(r["warnings"])
    p = diag["pup"]
    if p["root"] and not p["packs"] and not p["screens_at_root"]:
        out.append("pack PuP sans screens.pup : incomplet")
    if p["packs"] and p["alias_ok"] is False:
        out.append("dossier du pack (" + ", ".join(p["packs"][:2]) + ") ne porte pas le nom de la ROM : le lanceur pose un lien")
    if diag["broken"]:
        out.append("table marquee « broken » dans VPS")
    return out


def scan_tables(tables_root: Path, db: list, apply: bool = False) -> list[dict]:
    rows = []
    try:
        dirs = sorted(d for d in Path(tables_root).iterdir() if d.is_dir() and any(d.glob("*.vpx")))
    except OSError:
        return rows
    for d in dirs:
        res = identify(d, db)
        if apply and res["status"] == "ok":
            res["applied"] = apply_manifest(d, res)
        entry = entry_by_id(db, res["entry"]["id"]) if res.get("entry") else None
        diag = diagnostic(d, entry, res.get("rom", ""))
        res["diag"] = diag
        res["problemes"] = problemes(diag)
        rows.append(res)
    return rows


# --- CLI ----------------------------------------------------------------------
def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}
    cmd = args[0] if args else "status"
    js = "--json" in flags
    if cmd == "status":
        st = db_status()
        print(json.dumps(st, indent=2) if js else f"base VPS : {'presente' if st['present'] else 'absente'} · {st['entries']} entrees · age {st['age_days']} j · {'a rafraichir' if st.get('stale') else 'a jour'}")
        return 0
    if cmd == "refresh":
        try:
            r = refresh(force="--force" in flags)
        except Exception as exc:
            print(f"ERREUR: telechargement impossible ({exc})", file=sys.stderr)
            return 1
        print(json.dumps(r, indent=2) if js else f"base VPS : {r['reason']} · {r['entries']} entrees")
        return 0
    db = load_db()
    if not db:
        print("ERREUR: base VPS absente, lancer `pincabos-vps refresh`", file=sys.stderr)
        return 1
    if cmd == "identify":
        dirs = [Path(a) for a in args[1:]] or None
        if dirs:
            rows = []
            for d in dirs:
                res = identify(d, db)
                if "--apply" in flags and res["status"] == "ok":
                    res["applied"] = apply_manifest(d, res, force="--force" in flags)
                rows.append(res)
        else:
            rows = scan_tables(TABLES_ROOT, db, apply="--apply" in flags)
        if js:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            for r in rows:
                e = r.get("entry") or {}
                etat = {"ok": "OK ", "ambigu": "?? ", "aucun": "-- "}[r["status"]]
                print(f"{etat}{r['folder'][:48]:<48} {e.get('id', ''):<11} {r['how']:<22} {'ecrit' if r.get('applied') else ''}")
                for pb in r.get("problemes", []):
                    print("      ! " + pb)
        return 0
    if cmd == "diag" and len(args) > 1:
        d = Path(args[1])
        res = identify(d, db)
        entry = entry_by_id(db, res["entry"]["id"]) if res.get("entry") else None
        diag = diagnostic(d, entry, res.get("rom", ""))
        print(json.dumps({"identification": res, "diagnostic": diag, "problemes": problemes(diag)}, indent=2, ensure_ascii=False))
        return 0
    print(__doc__)
    print("usage : pincabos-vps status | refresh [--force] | identify [--apply] [--force] [--json] [dossier...] | diag <dossier>")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
