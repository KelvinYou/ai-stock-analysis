"""Display contracts use synthetic public prices, never owner data."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "allocation_export", Path(__file__).parents[1] / "scripts/export_allocation_research.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample():
    return {
        "period_log": [
            {
                "entry_date": "2025-01-02",
                "exit_date": "2025-02-03",
                "as_of_date": "2024-12-31",
                "selected_tickers": ["AAA", "BBB", "CCC"],
                "net_return": 0.1,
                "strict_hold_net_return": 0.05,
            }
        ],
        "net_compound_return": 0.1,
        "buy_and_hold_return": 0.05,
        "excess_return": 0.05,
        "config": {"cost_bps_per_side": 20},
        "universe": ["AAA", "BBB", "CCC"],
        "periods": 1,
        "effective_n": 1,
        "price_basis": "synthetic",
        "strict_hold_log_excess_ci_95": [-0.01, 0.02],
        "max_drawdown": -0.1,
        "buy_and_hold_max_drawdown": -0.05,
        "secret_provider_payload": "MUST_NOT_EXPORT",
    }


def test_export_reconciles_fraction_units_and_preserves_absent_ai():
    view = module.monthly(sample(), {"id": "synthetic", "label": "Synthetic"})
    assert view["curve"][-1]["allocator"] == pytest.approx(110)
    assert view["curve"][-1]["reference"] == pytest.approx(105)
    assert view["arms"][0]["net_return"] == 0.1
    assert view["arms"][2]["status"] == "not_tested"
    assert view["arms"][2]["net_return"] is None
    assert "secret_provider_payload" not in view


def test_inconsistent_source_return_is_rejected():
    raw = sample()
    raw["net_compound_return"] = 0.8
    with pytest.raises(ValueError, match="reconcile"):
        module.monthly(raw, {"id": "synthetic", "label": "Synthetic"})


@pytest.mark.parametrize("returns", [[float("nan")], [-1], [float("inf")]])
def test_nonfinite_or_unrepresentable_paths_are_rejected(returns):
    with pytest.raises(ValueError):
        module.curve(sample()["period_log"], returns, [0.1])


def test_incomplete_curve_is_rejected():
    with pytest.raises(ValueError, match="coverage"):
        module.curve(sample()["period_log"], [], [0.1])


@pytest.mark.parametrize("source", ["changed.json", "../outside.json"])
def test_manifest_rejects_changed_or_outside_sources(tmp_path, monkeypatch, source):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "changed.json").write_text(json.dumps(sample()))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "experiments": [
                    {
                        "id": "synthetic",
                        "source": source,
                        "sha256": "0" * 64,
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(module, "REPORTS", reports)
    monkeypatch.setattr(module, "MANIFEST", manifest)
    with pytest.raises(ValueError, match=r"hash changed|approved research"):
        module.export()
