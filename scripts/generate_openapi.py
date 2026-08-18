#!/usr/bin/env python3
"""Generate or verify the FastAPI OpenAPI contract snapshot.

The running application remains the source of truth.  This snapshot exists so
reviewers and CI can detect an accidental route or response-model change
before a web client or Postman collection consumes it.

Usage:
    python scripts/generate_openapi.py
    python scripts/generate_openapi.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from stock_analysis.api.app import app

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "contracts" / "openapi.json"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _resolve_output(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="snapshot path (relative paths are resolved from the repository root)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 when the snapshot differs from the running app",
    )
    args = parser.parse_args()
    output = _resolve_output(args.output)
    rendered = _canonical_json(app.openapi())

    if args.check:
        if not output.exists():
            print(f"missing OpenAPI snapshot: {output}", file=sys.stderr)
            return 1
        if output.read_text() != rendered:
            print(
                f"{output} is out of date — run: python scripts/generate_openapi.py",
                file=sys.stderr,
            )
            return 1
        print(f"{output} is up to date")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_text() == rendered:
        print(f"{output} already up to date")
        return 0
    output.write_text(rendered)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
