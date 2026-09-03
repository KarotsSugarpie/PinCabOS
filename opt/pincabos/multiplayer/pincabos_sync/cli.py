"""CLI de diagnostic seulement; aucun daemon ni lancement de table."""

from __future__ import annotations

import argparse
import json

from .audit import read_only_audit
from .pcosrec import verify_file


def main() -> int:
    parser = argparse.ArgumentParser(prog="pincabos-sync-dev")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="audit protégé en lecture seule")
    audit.add_argument("--json", action="store_true")
    verify = subparsers.add_parser("verify-record", help="valide un PCOSREC v0")
    verify.add_argument("path")
    args = parser.parse_args()
    result = read_only_audit() if args.command == "audit" else verify_file(args.path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
