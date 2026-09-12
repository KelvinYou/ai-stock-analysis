"""The data-health sweep writes to real per-ticker data, so it is tested.

`repair_ticker` rewrites `price_history.csv` and `technicals.json` in place.
The rules it applies live in `data/bars.py` and are tested there; these tests
cover what the script itself owns: what it touches, what it leaves alone, and
that it does not paper over a stale briefing.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_data_health.py"
_spec = importlib.util.spec_from_file_location("audit_data_health", _SCRIPT)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def _csv_rows(n: int = 40, volume: int = 15_000_000) -> list[str]:
    rows = []
    for i in range(n):
        day = date(2026, 1, 1) + timedelta(days=i)
        close = 100.0 + i * 0.5
        rows.append(f"{day},{close - 1},{close + 1},{close - 2},{close},{volume}")
    return rows


def _write_ticker(base: Path, symbol: str, rows: list[str]) -> Path:
    d = base / symbol
    d.mkdir(parents=True)
    (d / "price_history.csv").write_text(
        "date,open,high,low,close,volume\n" + "\n".join(rows) + "\n"
    )
    return d


def test_clean_ticker_is_left_untouched(tmp_path) -> None:
    d = _write_ticker(tmp_path, "CLEAN", _csv_rows())
    before = (d / "price_history.csv").read_text()

    assert audit.scan_ticker(d) == []
    assert audit.repair_ticker(d) is None
    assert (d / "price_history.csv").read_text() == before
    assert not (d / "technicals.json").exists()


def test_nan_row_is_reported_then_dropped(tmp_path) -> None:
    rows = _csv_rows()
    rows[20] = "2026-01-21,nan,nan,nan,nan,15573685"
    d = _write_ticker(tmp_path, "BADBAR", rows)

    findings = audit.scan_ticker(d)
    assert any("unusable bar" in f and "2026-01-21" in f for f in findings)

    note = audit.repair_ticker(d)
    assert note is not None and "dropped 1 bar" in note

    assert "nan" not in (d / "price_history.csv").read_text().lower()
    assert audit.scan_ticker(d) == []
    # Technicals are recomputed from the repaired series, not left behind.
    snapshot = json.loads((d / "technicals.json").read_text())
    assert snapshot["sma_20"] is not None
    assert snapshot["rsi_14"] is not None


def test_provisional_tail_is_reported_then_dropped(tmp_path) -> None:
    rows = _csv_rows()
    rows[-1] = "2026-02-09,120.0,121.0,119.0,120.0,1936755"  # 12.9% of median
    d = _write_ticker(tmp_path, "THINTAIL", rows)

    findings = audit.scan_ticker(d)
    assert any("provisional bar" in f for f in findings)

    audit.repair_ticker(d)

    csv_text = (d / "price_history.csv").read_text()
    assert "2026-02-09" not in csv_text
    assert audit.scan_ticker(d) == []


def test_a_ticker_with_only_bad_bars_is_not_emptied(tmp_path) -> None:
    d = _write_ticker(tmp_path, "ALLBAD", ["2026-01-02,nan,nan,nan,nan,100"])

    note = audit.repair_ticker(d)

    assert note is not None and "CANNOT FIX" in note
    assert "nan" in (d / "price_history.csv").read_text().lower()


def test_stale_briefing_is_reported_and_never_silently_repaired(tmp_path) -> None:
    d = _write_ticker(tmp_path, "STALE", _csv_rows())
    (d / "briefing.json").write_text(
        json.dumps({"ticker": "STALE", "date": "2026-01-20", "data_as_of": "2026-01-19"})
    )
    (d / "technicals.json").write_text(json.dumps({"as_of_date": "2026-02-09"}))
    before = (d / "briefing.json").read_text()

    findings = audit.scan_ticker(d)

    assert any("stale briefing" in f for f in findings)
    assert any("rerun: stock-analysis STALE" in f for f in findings)
    # No bar defects, so nothing is rewritten — and the briefing is never
    # re-dated to look current.
    assert audit.repair_ticker(d) is None
    assert (d / "briefing.json").read_text() == before


def test_repair_leaves_the_briefing_flagged_stale(tmp_path) -> None:
    """Fixing the bars does not make an old verdict current."""
    rows = _csv_rows()
    rows[-1] = "2026-02-09,120.0,121.0,119.0,120.0,1000"
    d = _write_ticker(tmp_path, "BOTH", rows)
    (d / "briefing.json").write_text(
        json.dumps({"ticker": "BOTH", "date": "2026-01-20", "data_as_of": "2026-01-19"})
    )

    assert audit.repair_ticker(d) is not None

    findings = audit.scan_ticker(d)
    assert all("unusable" not in f and "provisional" not in f for f in findings)
    assert any("stale briefing" in f for f in findings)


def test_missing_data_dir_exits_nonzero(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv", ["audit_data_health.py", "--data-dir", str(tmp_path / "nope")]
    )
    assert audit.main() == 1


def test_exit_code_is_zero_only_when_nothing_is_wrong(tmp_path, monkeypatch) -> None:
    _write_ticker(tmp_path, "CLEAN", _csv_rows())
    monkeypatch.setattr("sys.argv", ["audit_data_health.py", "--data-dir", str(tmp_path)])
    assert audit.main() == 0

    rows = _csv_rows()
    rows[5] = "2026-01-06,nan,nan,nan,nan,1"
    _write_ticker(tmp_path, "DIRTY", rows)
    assert audit.main() == 1


@pytest.mark.parametrize("filename", ["price_history.csv", "briefing.json"])
def test_scan_tolerates_a_ticker_missing_files(tmp_path, filename) -> None:
    d = tmp_path / "SPARSE"
    d.mkdir()
    if filename == "briefing.json":
        (d / "price_history.csv").write_text("date,open,high,low,close,volume\n")
    assert audit.scan_ticker(d) == []
