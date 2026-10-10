import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from stock_analysis.backtest.prospective import freeze, score, verify


def _cohort(tmp_path):
    predictions = tmp_path / "predictions.json"
    predictions.write_text("[]")
    protocol = {
        "hashes": {"predictions.json": hashlib.sha256(predictions.read_bytes()).hexdigest()},
        "score_not_before_utc": (datetime.now(UTC).date() + timedelta(days=30)).isoformat(),
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(protocol))
    (tmp_path / "manifest.sha256").write_text(hashlib.sha256(manifest.read_bytes()).hexdigest())
    return tmp_path


def test_modified_predictions_are_rejected_before_scoring(tmp_path):
    cohort = _cohort(tmp_path)
    (cohort / "predictions.json").write_text('[{"ticker":"CHANGED"}]')
    with pytest.raises(ValueError, match="Frozen artifact changed"):
        verify(cohort)


def test_immature_cohort_never_reads_prices(tmp_path, monkeypatch):
    cohort = _cohort(tmp_path)
    monkeypatch.setattr(
        "stock_analysis.backtest.prospective.Backtester._fetch_price_series",
        lambda *args: pytest.fail("premature outcome fetch"),
    )
    with pytest.raises(ValueError, match="not mature"):
        score(cohort)


def test_backdated_freeze_cannot_be_called_prospective(tmp_path):
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    with pytest.raises(ValueError, match="Freeze must be today"):
        freeze(tmp_path, tmp_path / "cohort", forecast_date=yesterday)
    assert not (tmp_path / "cohort").exists()
