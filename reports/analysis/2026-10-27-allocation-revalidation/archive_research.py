"""Archive actual in-session evidence and refresh current research provenance.

Run only after finalize_briefing.py has saved all three real briefings.
"""

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
WORK = Path("/private/tmp/allocation-20261027")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    archive = OUT / "research"
    archive.mkdir(exist_ok=True)
    sources = {}
    for role in ("fundamentals", "sentiment", "macro"):
        path = WORK / f"{role}-evidence.json"
        shutil.copy2(path, archive / path.name)
        sources[role] = json.loads(path.read_text())
    prompts = [ROOT / "src/stock_analysis" / path for path in (
        "agents/fundamentals.py", "agents/sentiment.py", "agents/technical.py", "agents/macro.py",
        "debate/engine.py", "debate/research_manager.py", "synthesis/synthesizer.py")]
    for ticker in ("TSM", "V", "UNH"):
        folder = archive / ticker
        folder.mkdir(exist_ok=True)
        for stage in ("fundamentals", "sentiment", "technical", "macro", "analysts",
                      "debate", "verdict", "synthesis"):
            shutil.copy2(WORK / f"{ticker}-{stage}.json", folder / f"{stage}.json")
        data = ROOT / "data" / ticker
        inputs = folder / "inputs"
        inputs.mkdir(exist_ok=True)
        for name in ("fundamentals.json", "price_history.csv"):
            shutil.copy2(data / name, inputs / name)
        # Technical snapshot metadata is sufficient to inspect the analyst's inputs;
        # exact full series remains hashed in the current data directory.
        technical = json.loads((data / "technicals.json").read_text())
        technical.pop("series", None)
        (inputs / "technicals.json").write_text(json.dumps(technical, indent=2) + "\n")
        for name in ("briefing.json", "analyst_reports.json", "debate_result.json", "research_verdict.json"):
            shutil.copy2(data / name, folder / name)
        briefing = json.loads((data / "briefing.json").read_text())
        provenance = {
            "symbol": ticker, "date": briefing["date"], "data_as_of": briefing["data_as_of"],
            "mode": "in-session", "recorded_at_utc": datetime.now(UTC).isoformat(),
            "model_identity": "Current Codex conversation; exact model identifier not exposed",
            "authenticated_provider_attestation": False,
            "input_sha256": {name: sha(data / name) for name in
                             ("fundamentals.json", "price_history.csv", "technicals.json")},
            "prompt_source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in prompts},
            "role_report_sha256": {role: sha(folder / f"{role}.json") for role in
                                   ("fundamentals", "sentiment", "technical", "macro")},
            "artifact_sha256": {name: sha(data / name) for name in
                                ("briefing.json", "analyst_reports.json", "debate_result.json", "research_verdict.json")},
            "source_evidence": sources,
            "research_archive": str(folder.relative_to(ROOT)),
            "scope": "Current research, not a sealed prospective backtest forecast or trading order",
            "macro_contract": "No typed macro snapshot; neutral/low retained despite separate official context",
            "storage": "Local files; no Supabase publication performed",
        }
        payload = json.dumps(provenance, indent=2, allow_nan=False) + "\n"
        (folder / "analysis_provenance.json").write_text(payload)
        (data / "analysis_provenance.json").write_text(payload)
        print(f"Archived {ticker}: {briefing['overall_signal']}, convergence {briefing['conviction']['signal_convergence']}")


if __name__ == "__main__":
    main()
