"""Refresh the approved current price preview from a fully fetched local panel.

Use the repo venv. --prices-dir defaults to the public child repo's data/.
No network, AI calls, personal holdings or order submission.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from export_allocation_research import MANIFEST, REPORTS, ROOT

from stock_analysis.allocation_snapshot import build_current_momentum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    primary = next(x for x in manifest["experiments"] if x["id"] == manifest["default_id"])
    source = (REPORTS / primary["source"]).resolve()
    if (
        not source.is_relative_to(REPORTS.resolve())
        or hashlib.sha256(source.read_bytes()).hexdigest() != primary["sha256"]
    ):
        raise ValueError("Primary universe source could not be verified")
    universe = json.loads(source.read_text())["universe"]
    histories, hashes = {}, {}
    for ticker in universe:
        nested = args.prices_dir / ticker / "price_history.csv"
        path = nested if nested.exists() else args.prices_dir / f"{ticker}.csv"
        histories[ticker] = pd.read_csv(path)
        hashes[ticker] = hashlib.sha256(path.read_bytes()).hexdigest()
    now = datetime.now(UTC)
    snapshot = build_current_momentum(histories, today=now.date())
    if snapshot["status"] != "available":
        raise ValueError(snapshot["reason"])
    snapshot.update(
        captured_at_utc=now.isoformat(),
        input_hashes=hashes,
        price_source="Local public price panel; provider adjusted returns not independently verified",
    )
    target = REPORTS / f"{now.date()}-current-allocation" / "current-momentum.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, indent=2, allow_nan=False) + "\n"
    target.write_text(payload)
    item = {
        "id": "current_momentum",
        "source": str(target.relative_to(REPORTS)),
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }
    manifest["support"] = [x for x in manifest["support"] if x["id"] != item["id"]] + [item]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/export_allocation_research.py")], check=True
    )
    print(
        f"Current preview as of {snapshot['as_of']}: "
        + ", ".join(r["ticker"] for r in snapshot["ranking"][:3])
    )


if __name__ == "__main__":
    main()
