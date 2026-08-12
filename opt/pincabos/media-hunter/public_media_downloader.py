#!/usr/bin/env python3

import argparse
import hashlib
import logging
import os
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


USER_AGENT = "PinCabOS-MediaHunter/1.0"
MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".mp4", ".webm", ".mkv", ".avi", ".mov",
    ".mp3", ".wav", ".ogg", ".flac"
}

TYPE_RULES = {
    "fulldmd": ("fulldmd", "full-dmd", "full_dmd"),
    "backglass": ("backglass", "back-glass", "back_glass", "bg video"),
    "playfield": ("playfield", "table video", "table-video"),
    "wheel": ("wheel", "logo"),
    "topper": ("topper",),
    "dmd": ("dmd",),
    "audio": ("audio", "table sound", "launch audio"),
}


def sanitize_filename(name: str) -> str:
    name = unquote(name).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:220] or "unnamed-media"


def classify_media(url: str, filename: str) -> str:
    text = f"{url} {filename}".lower()

    # FullDMD doit être testé avant DMD.
    for media_type in (
        "fulldmd",
        "backglass",
        "playfield",
        "wheel",
        "topper",
        "audio",
        "dmd",
    ):
        if any(keyword in text for keyword in TYPE_RULES[media_type]):
            return media_type

    return "other"


def media_extension(url: str) -> str:
    return Path(urlparse(url).path).suffix.lower()


def robots_allowed(session: requests.Session, url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    parser = RobotFileParser()
    parser.set_url(robots_url)

    try:
        response = session.get(robots_url, timeout=15)
        if response.status_code >= 400:
            return True

        parser.parse(response.text.splitlines())
        return parser.can_fetch(USER_AGENT, url)
    except requests.RequestException:
        # En cas d’échec du robots.txt, on demeure prudent,
        # mais on permet la page publique demandée explicitement.
        return True


def filename_from_response(url: str, response: requests.Response) -> str:
    disposition = response.headers.get("content-disposition", "")

    match = re.search(
        r"filename\*=UTF-8''([^;]+)",
        disposition,
        flags=re.IGNORECASE,
    )
    if match:
        return sanitize_filename(match.group(1))

    match = re.search(
        r'filename="?([^";]+)"?',
        disposition,
        flags=re.IGNORECASE,
    )
    if match:
        return sanitize_filename(match.group(1))

    name = Path(urlparse(url).path).name
    return sanitize_filename(name)


def unique_path(directory: Path, filename: str, url: str) -> Path:
    destination = directory / filename

    if not destination.exists():
        return destination

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    stem = destination.stem
    suffix = destination.suffix
    return directory / f"{stem}-{digest}{suffix}"


def download_file(
    session: requests.Session,
    url: str,
    output_root: Path,
    max_size_mb: int,
) -> None:
    try:
        with session.get(url, stream=True, timeout=60, allow_redirects=True) as response:
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            extension = media_extension(response.url)

            if extension not in MEDIA_EXTENSIONS and not (
                content_type.startswith("image/")
                or content_type.startswith("video/")
                or content_type.startswith("audio/")
            ):
                return

            content_length = response.headers.get("content-length")
            maximum_bytes = max_size_mb * 1024 * 1024

            if content_length and int(content_length) > maximum_bytes:
                logging.warning("IGNORÉ trop volumineux : %s", response.url)
                return

            filename = filename_from_response(response.url, response)

            if not Path(filename).suffix and extension:
                filename += extension

            media_type = classify_media(response.url, filename)
            directory = output_root / media_type
            directory.mkdir(parents=True, exist_ok=True)

            destination = unique_path(directory, filename, response.url)
            temporary = destination.with_suffix(destination.suffix + ".part")

            downloaded = 0

            with temporary.open("wb") as file_handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue

                    downloaded += len(chunk)

                    if downloaded > maximum_bytes:
                        file_handle.close()
                        temporary.unlink(missing_ok=True)
                        logging.warning("IGNORÉ limite dépassée : %s", response.url)
                        return

                    file_handle.write(chunk)

            temporary.replace(destination)
            logging.info("GO [%s] %s", media_type.upper(), destination)

    except requests.RequestException as error:
        logging.error("Erreur téléchargement %s : %s", url, error)


def crawl(
    start_url: str,
    output_root: Path,
    maximum_pages: int,
    delay_seconds: float,
    max_size_mb: int,
) -> None:
    parsed_start = urlparse(start_url)

    if parsed_start.scheme not in {"http", "https"}:
        raise ValueError("L’adresse doit commencer par http:// ou https://")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    if not robots_allowed(session, start_url):
        raise RuntimeError("robots.txt interdit l’exploration de cette adresse.")

    allowed_domain = parsed_start.netloc.lower()
    queue = deque([start_url])
    visited_pages = set()
    discovered_media = set()

    while queue and len(visited_pages) < maximum_pages:
        current_url = queue.popleft()

        if current_url in visited_pages:
            continue

        if not robots_allowed(session, current_url):
            logging.warning("ROBOTS interdit : %s", current_url)
            continue

        logging.info(
            "PAGE %d/%d : %s",
            len(visited_pages) + 1,
            maximum_pages,
            current_url,
        )

        try:
            response = session.get(current_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as error:
            logging.error("Erreur page %s : %s", current_url, error)
            continue

        visited_pages.add(current_url)

        content_type = response.headers.get("content-type", "").lower()

        if not content_type.startswith("text/html"):
            if media_extension(response.url) in MEDIA_EXTENSIONS:
                download_file(
                    session,
                    response.url,
                    output_root,
                    max_size_mb,
                )
            time.sleep(delay_seconds)
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        candidates = []

        for element, attribute in (
            ("a", "href"),
            ("img", "src"),
            ("video", "src"),
            ("audio", "src"),
            ("source", "src"),
        ):
            for item in soup.find_all(element):
                value = item.get(attribute)
                if value:
                    candidates.append(value)

        for candidate in candidates:
            absolute_url = urljoin(current_url, candidate)
            parsed = urlparse(absolute_url)

            if parsed.scheme not in {"http", "https"}:
                continue

            clean_url = parsed._replace(fragment="").geturl()
            extension = media_extension(clean_url)

            if extension in MEDIA_EXTENSIONS:
                if clean_url not in discovered_media:
                    discovered_media.add(clean_url)
                    download_file(
                        session,
                        clean_url,
                        output_root,
                        max_size_mb,
                    )
                    time.sleep(delay_seconds)
                continue

            if (
                parsed.netloc.lower() == allowed_domain
                and clean_url not in visited_pages
            ):
                queue.append(clean_url)

        time.sleep(delay_seconds)

    logging.info(
        "TERMINÉ : %d pages et %d médias détectés.",
        len(visited_pages),
        len(discovered_media),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Téléchargeur responsable de médias publics pour PinCabOS."
    )
    parser.add_argument("url", help="Page publique de départ")
    parser.add_argument(
        "--output",
        default="/home/pinball/MediaHunter/downloads",
        help="Dossier de destination",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=30,
        help="Nombre maximum de pages",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Délai entre les requêtes en secondes",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=750,
        help="Taille maximale d’un média en Mo",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    output_root = Path(args.output).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    crawl(
        start_url=args.url,
        output_root=output_root,
        maximum_pages=max(1, min(args.pages, 500)),
        delay_seconds=max(1.0, args.delay),
        max_size_mb=max(1, args.max_size),
    )


if __name__ == "__main__":
    main()
