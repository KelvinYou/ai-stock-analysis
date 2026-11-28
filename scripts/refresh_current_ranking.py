"""Pin today's price-only ranking for every price rule from the local price panel.

Use the repo venv. No network, AI calls, personal holdings or order submission.
Fetch prices first with `STORAGE_BACKEND=local stock-fetch ...`.
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

from stock_analysis.current_ranking import build_current_ranking


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    universes, histories, hashes = {}, {}, {}
    for item in manifest["strategy_comparisons"]:
        source = (REPORTS / item["source"]).resolve()
        if (
            not source.is_relative_to(REPORTS.resolve())
            or hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise ValueError(f"Universe source could not be verified: {item['id']}")
        universes[item["id"]] = json.loads(source.read_text())["universe"]
    for ticker in sorted({t for u in universes.values() for t in u}):
        path = args.prices_dir / ticker / "price_history.csv"
        histories[ticker] = pd.read_csv(path)
        hashes[ticker] = hashlib.sha256(path.read_bytes()).hexdigest()
    now = datetime.now(UTC)
    ranking = build_current_ranking(histories, universes=universes, today=now.date())
    if ranking["status"] != "available":
        raise ValueError(ranking["reason"])
    ranking.update(
        captured_at_utc=now.isoformat(),
        input_hashes=hashes,
        price_source="Local public price panel; provider adjusted returns not independently verified",
    )
    target = REPORTS / f"{now.date()}-current-ranking" / "current-ranking.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(ranking, indent=2, allow_nan=False) + "\n"
    target.write_text(payload)
    item = {
        "id": "current_ranking",
        "source": str(target.relative_to(REPORTS)),
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }
    manifest["support"] = [x for x in manifest["support"] if x["id"] != item["id"]] + [item]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/export_allocation_research.py")], check=True
    )
    print(f"Pinned {target.relative_to(ROOT)} as of {ranking['as_of']}")


if __name__ == "__main__":
    main()
