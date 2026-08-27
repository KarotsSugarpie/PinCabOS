#!/usr/bin/env python3
"""
PinCabOS Smart Import — recherche locale VPSDB compacte.

Ne retourne jamais les énormes listes B2S, sons, images ou liens.
Le WebApp reçoit uniquement les champs nécessaires à la sélection.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

VPSDB_PATH = Path("/home/pinball/.config/vpinfe/vpsdb.json")
DEFAULT_LIMIT = 8


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def flatten(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, dict):
        out: list[str] = []
        for key, item in value.items():
            out.append(str(key))
            out.extend(flatten(item))
        return out

    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(flatten(item))
        return out

    return [str(value)]


def load_entries() -> list[dict[str, Any]]:
    with VPSDB_PATH.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    if not isinstance(raw, list):
        raise ValueError("vpsdb.json doit être une liste JSON.")

    return [entry for entry in raw if isinstance(entry, dict)]


def score_entry(entry: dict[str, Any], query: str, rom: str) -> int:
    query_n = norm(query)
    rom_n = norm(rom)

    name_n = norm(entry.get("name"))
    id_n = norm(entry.get("id"))
    blob_n = norm(" ".join(flatten(entry)))

    points = 0

    if query_n:
        if query_n == id_n:
            points += 1_000_000

        if query_n == name_n:
            points += 500_000
        elif query_n in name_n:
            points += 180_000

        wanted = set(query_n.split())
        words = set(name_n.split())
        overlap = wanted & words

        if overlap:
            points += len(overlap) * 12_000

        if wanted and wanted == words:
            points += 100_000

        if query_n in blob_n:
            points += 1_000

    if rom_n and rom_n in blob_n:
        points += 20_000

    return points


def compact_entry(entry: dict[str, Any], points: int) -> dict[str, Any]:
    title = str(entry.get("name") or "").strip()
    ident = str(entry.get("id") or "").strip()
    manufacturer = str(entry.get("manufacturer") or "").strip()
    year = str(entry.get("year") or "").strip()

    suffix = " ".join(value for value in (manufacturer, year) if value)
    final_name = f"{title} ({suffix})" if suffix else title

    return {
        "id": ident,
        "vpsid": ident,
        "vpsId": ident,
        "title": title,
        "name": title,
        "table_name": title,
        "tableName": title,
        "table_title": title,
        "final_table_name": final_name,
        "manufacturer": manufacturer,
        "year": year,
        "rom": "",
        "score": str(points),
        "pincabosMatchScore": points,
        "broken": bool(entry.get("broken", False)),
        "game": {
            "id": ident,
            "name": title,
        },
    }


def compact_table_file(
    entry: dict[str, Any],
    table_file: dict[str, Any],
    points: int,
) -> dict[str, Any]:
    result = compact_entry(entry, points)
    table_vpsid = str(table_file.get("id") or "").strip()
    parent_vpsid = str(table_file.get("parentId") or "").strip()
    parent_version = ""

    if parent_vpsid:
        for candidate in entry.get("tableFiles", []):
            if (
                isinstance(candidate, dict)
                and str(candidate.get("id") or "").strip() == parent_vpsid
            ):
                parent_version = str(candidate.get("version") or "").strip()
                break

    result.update({
        "id": table_vpsid,
        "vpsid": table_vpsid,
        "vpsId": table_vpsid,
        "game_vpsid": str(entry.get("id") or "").strip(),
        "parent_vpsid": parent_vpsid,
        "parent_version": parent_version,
        "version": str(table_file.get("version") or "").strip(),
        "features": [
            str(value)
            for value in table_file.get("features", [])
            if str(value).strip()
        ],
        "comment": str(table_file.get("comment") or "").strip(),
        "resource_type": "tableFile",
        "game": {
            "id": str(entry.get("id") or "").strip(),
            "name": str(entry.get("name") or "").strip(),
        },
    })

    return result


def matches(entries: list[dict[str, Any]], query: str, rom: str, limit: int) -> list[dict[str, Any]]:
    query_n = norm(query)

    # Un identifiant de fichier de table (par exemple un mod .dif) doit
    # conserver son propre VPSId et sa relation parentId. L'ancien matcher
    # ramenait seulement l'identifiant générique du jeu, ce qui empêchait de
    # prouver qu'un patch ciblait bien la table installée.
    exact_table_files: list[dict[str, Any]] = []

    if query_n:
        for entry in entries:
            for table_file in entry.get("tableFiles", []):
                if not isinstance(table_file, dict):
                    continue

                if norm(table_file.get("id")) == query_n:
                    exact_table_files.append(
                        compact_table_file(
                            entry,
                            table_file,
                            1_500_000,
                        )
                    )

    if exact_table_files:
        return exact_table_files[:max(1, min(limit, 20))]

    exact_id = [
        entry for entry in entries
        if query_n and norm(entry.get("id")) == query_n
    ]

    pool = exact_id if exact_id else entries
    ranked: list[tuple[int, str, str, dict[str, Any]]] = []

    for entry in pool:
        points = score_entry(entry, query, rom)

        if points <= 0:
            continue

        result = compact_entry(entry, points)
        ranked.append((
            points,
            norm(result["title"]),
            result["id"],
            result,
        ))

    ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
    return [row[3] for row in ranked[:max(1, min(limit, 20))]]


def parse_input() -> tuple[str, str, int]:
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("query_positional", nargs="?")
    parser.add_argument("rom_positional", nargs="?")
    parser.add_argument("--query", "--table", "--table-name", dest="query")
    parser.add_argument("--rom", dest="rom")
    parser.add_argument("--vpsid", "--id", dest="vpsid")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)

    args, _unknown = parser.parse_known_args()

    query = args.vpsid or args.query or args.query_positional or ""
    rom = args.rom or args.rom_positional or ""

    return query.strip(), rom.strip(), args.limit


def emit(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def main() -> int:
    try:
        query, rom, limit = parse_input()

        if not query and not rom:
            emit({
                "ok": True,
                "matches": [],
                "results": [],
                "count": 0,
                "source": str(VPSDB_PATH),
            })
            return 0

        entries = load_entries()
        rows = matches(entries, query, rom, limit)

        emit({
            "ok": True,
            "matches": rows,
            "results": rows,
            "count": len(rows),
            "source": str(VPSDB_PATH),
        })
        return 0

    except Exception as exc:
        emit({
            "ok": False,
            "matches": [],
            "results": [],
            "count": 0,
            "source": str(VPSDB_PATH),
            "error": f"{type(exc).__name__}: {exc}",
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
