"""Export allowlisted public research, never private holdings or model payloads."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/analysis"
MANIFEST = ROOT / "config/allocation_research.json"


def curve(periods: list[dict], candidate: list[float], baseline: list[float]) -> list[dict]:
    if not periods or not (len(periods) == len(candidate) == len(baseline)):
        raise ValueError("Incomplete curve coverage")
    a = b = 100.0
    points = [
        {"date": periods[0]["entry_date"], "allocator": a, "reference": b, "log_excess": None}
    ]
    for period, ra, rb in zip(periods, candidate, baseline, strict=True):
        if not all(math.isfinite(x) and x > -1 for x in (ra, rb)):
            raise ValueError("Invalid return")
        a *= 1 + ra
        b *= 1 + rb
        points.append(
            {
                "date": period["exit_date"],
                "allocator": a,
                "reference": b,
                "log_excess": math.log1p(ra) - math.log1p(rb),
            }
        )
    return points


def arm(key, label, value=None, dd=None, exposure=None, status="available"):
    return {
        "id": key,
        "label": label,
        "status": status,
        "net_return": value,
        "drawdown": dd,
        "mean_exposure": exposure,
    }


def monthly(raw: dict, item: dict) -> dict:
    p = raw["period_log"]
    points = curve(p, [x["net_return"] for x in p], [x["strict_hold_net_return"] for x in p])
    for key, value in [
        ("allocator", raw["net_compound_return"]),
        ("reference", raw["buy_and_hold_return"]),
    ]:
        if not math.isclose(points[-1][key] / 100 - 1, value, abs_tol=1e-9):
            raise ValueError("Curve does not reconcile to reported return")
    return {
        "id": item["id"],
        "label": item["label"],
        "kind": "monthly",
        "excess_vs_hold": raw["excess_return"],
        "cost_bps": raw["config"]["cost_bps_per_side"],
        "universe": raw["universe"],
        "start": p[0]["entry_date"],
        "end": p[-1]["exit_date"],
        "periods": raw["periods"],
        "effective_n": raw["effective_n"],
        "drawdown_basis": "Daily close marks",
        "price_basis": raw["price_basis"],
        "fee_basis": "Turnover fees; final liquidation included",
        "reference_label": "Continuous hold",
        "ci_reference": "Continuous hold",
        "ci": raw["strict_hold_log_excess_ci_95"],
        "curve": points,
        "last_selection": {"as_of": p[-1]["as_of_date"], "tickers": p[-1]["selected_tickers"]},
        "arms": [
            arm(
                "allocator_only",
                "Momentum allocator",
                raw["net_compound_return"],
                raw["max_drawdown"],
            ),
            arm(
                "continuous_strict_hold",
                "Continuous hold",
                raw["buy_and_hold_return"],
                raw["buy_and_hold_max_drawdown"],
            ),
            arm("ai_only", "AI only", status="not_tested"),
            arm("allocator_plus_ai", "Allocator + AI", status="not_tested"),
        ],
        "notes": [
            "Monthly observations, not a daily equity curve.",
            "Same surviving eight-stock universe; history has already been inspected.",
            "No AI forecasts were tested in this monthly experiment.",
            "Trade count and average exposure are not recorded in this report.",
        ],
    }


def episodes(raw: dict, item: dict) -> dict:
    e = raw["episodes"]
    a = e["allocator"]
    p = a["period_log"]
    views = e["signal_views"]["ai"]
    rows = e["period_returns"]
    ai = views["ai_only"]
    hybrid = views["hybrid"]
    points = curve(p, rows["allocator_only"], rows["scheduled_passive"])
    for key, value in [
        ("allocator", a["net_compound_return"]),
        ("reference", a["matched_passive_return"]),
    ]:
        if not math.isclose(points[-1][key] / 100 - 1, value, abs_tol=1e-9):
            raise ValueError("Episode curve mismatch")
    return {
        "id": item["id"],
        "label": item["label"],
        "kind": "episodes",
        "excess_vs_hold": a["excess_return"],
        "cost_bps": a["config"]["cost_bps_per_side"],
        "universe": a["universe"],
        "start": p[0]["entry_date"],
        "end": p[-1]["exit_date"],
        "periods": a["periods"],
        "effective_n": a["effective_n"],
        "drawdown_basis": "Episode endpoints only",
        "price_basis": a["price_basis"],
        "fee_basis": "Multiplicative entry / exit fees; cash between episodes",
        "reference_label": "Scheduled passive",
        "ci_reference": "Scheduled passive",
        "ci": a["matched_passive_log_excess_ci_95"],
        "curve": points,
        "last_selection": {"as_of": p[-1]["as_of_date"], "tickers": p[-1]["selected_tickers"]},
        "arms": [
            arm(
                "allocator_only", "Momentum allocator", a["net_compound_return"], a["max_drawdown"]
            ),
            arm("continuous_strict_hold", "Continuous hold", a["buy_and_hold_return"]),
            arm("scheduled_passive", "Scheduled passive", a["matched_passive_return"]),
            arm(
                "ai_only",
                "AI only",
                ai["net_compound_return"],
                ai["max_drawdown"],
                ai["mean_exposure"],
            ),
            arm(
                "allocator_plus_ai",
                "Allocator + AI",
                hybrid["net_compound_return"],
                hybrid["max_drawdown"],
                hybrid["mean_exposure"],
            ),
        ],
        "notes": [
            "Nine non-overlapping episodes; this is a different schedule from monthly rebalancing.",
            "Continuous hold final return is available; its curve and drawdown are not exported here.",
            "The curve reference and confidence interval use scheduled passive, not continuous hold.",
            "AI is a buy-label veto: no positive final labels left any sleeve invested.",
            "Endpoint drawdown omits losses inside each episode.",
        ],
    }


def export() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    experiments = []
    for item in manifest["experiments"]:
        path = (REPORTS / item["source"]).resolve()
        if not path.is_relative_to(REPORTS.resolve()):
            raise ValueError("Source must be an approved research artifact")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"Source hash changed: {item['id']}")
        raw = json.loads(path.read_text())
        view = monthly(raw, item) if item["kind"] == "monthly" else episodes(raw, item)
        view["source_sha256"] = digest
        experiments.append(view)
    support = {}
    for item in manifest["support"]:
        path = (REPORTS / item["source"]).resolve()
        if not path.is_relative_to(REPORTS.resolve()):
            raise ValueError("Supporting source must be an approved research artifact")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Supporting source hash changed")
        support[item["id"]] = json.loads(path.read_text())
    roll = support["extended"]["rolling_24m"]
    cut = support["concentration"]["primary8"]["cuts"][1]
    result = {
        "robustness": {
            "rolling_wins": roll["winning_windows"],
            "rolling_windows": roll["windows"],
            "rolling_min": roll["minimum_relative_advantage"],
            "omitted_months": cut["k"],
            "omitted_allocator": cut["candidate_return_both_arms_omit_months"],
            "omitted_hold": cut["hold_return_both_arms_omit_months"],
        },
        "version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "default_id": manifest["default_id"],
        "experiments": experiments,
        "current_plan": {
            "status": "unavailable",
            "reason": "No pinned same-session plan is connected.",
        },
        "reliability_status": "Unconfirmed",
        "promotion_ready": False,
        "limitations": [
            "Costs are research assumptions, not broker-calibrated fees.",
            "Dividend, tax and terminal-return completeness remain unverified.",
            "Historical universe and prior strategy searches limit generalization.",
        ],
    }
    if result["default_id"] not in {x["id"] for x in experiments}:
        raise ValueError("Default experiment missing")
    return result


if __name__ == "__main__":
    target = ROOT / "web/data/allocation-research.json"
    payload = json.dumps(export(), indent=2, allow_nan=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload)
    target.with_suffix(".sha256").write_text(hashlib.sha256(payload.encode()).hexdigest() + "\n")
    print(f"Exported {target.relative_to(ROOT)}")
