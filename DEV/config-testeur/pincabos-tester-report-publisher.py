#!/usr/bin/env python3
"""Publish queued PinCabOS tester reports to GitHub using root gh auth."""

import base64
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = "KarotsSugarpie/PinCabOS"
BRANCH = "main"
DEST = "DEV/config-testeur"
ROOT = Path("/var/lib/pincabos-release/tester-reports")
INCOMING = ROOT / "incoming"
SENT = ROOT / "sent"
FAILED = ROOT / "failed"
NAME_RE = re.compile(r"^[a-z0-9._-]{1,220}-system-audit\.txt$")
MAX_BYTES = 600 * 1024


def log(message):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def gh_ready():
    result = subprocess.run(
        ["gh", "auth", "status", "-h", "github.com"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        env={**os.environ, "HOME": "/root", "GH_PROMPT_DISABLED": "1"},
    )
    return result.returncode == 0


def publish(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("invalid_file")
    if not NAME_RE.fullmatch(path.name):
        raise ValueError("invalid_filename")
    data = path.read_bytes()
    if not 256 <= len(data) <= MAX_BYTES:
        raise ValueError("invalid_size")

    api_path = f"repos/{REPO}/contents/{DEST}/{path.name}"
    payload = json.dumps(
        {
            "message": f"tester report: {path.name}",
            "content": base64.b64encode(data).decode("ascii"),
            "branch": BRANCH,
        },
        separators=(",", ":"),
    )
    result = subprocess.run(
        ["gh", "api", "--method", "PUT", api_path, "--input", "-"],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "HOME": "/root", "GH_PROMPT_DISABLED": "1"},
    )
    if result.returncode != 0:
        raise RuntimeError("github_publish_failed")
    response = json.loads(result.stdout or "{}")
    commit_sha = str(((response.get("commit") or {}).get("sha") or ""))
    if not commit_sha:
        raise RuntimeError("github_invalid_response")
    return commit_sha


def main():
    if os.geteuid() != 0:
        log("NOGO root_required")
        return 1
    for directory in (INCOMING, SENT, FAILED):
        directory.mkdir(parents=True, exist_ok=True)
    if not shutil.which("gh") or not gh_ready():
        log("NOGO github_cli_not_authenticated")
        return 2

    files = sorted(INCOMING.glob("*.txt"))
    if not files:
        return 0

    rc = 0
    for path in files:
        try:
            commit_sha = publish(path)
            destination = SENT / path.name
            path.replace(destination)
            (SENT / (path.name + ".commit")).write_text(commit_sha + "\n", encoding="utf-8")
            log(f"GO {path.name} commit={commit_sha}")
        except Exception as exc:
            rc = 3
            log(f"NOGO {path.name} error={type(exc).__name__}:{exc}")
            try:
                path.replace(FAILED / path.name)
            except OSError:
                pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
