"""Supabase outcome-memory backend.

The scoring and leakage semantics live in ``outcomes.py``. This module only
changes how records are loaded and appended, so local and cloud runs use the
same deterministic calibration code.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from stock_analysis.config import Settings
from stock_analysis.data.cloud import SupabaseRestClient

from .outcomes import (
    CalibrationSummary,
    OutcomeRecord,
    compute_calibration,
)


class SupabaseOutcomeStore:
    """Append-only outcome repository backed by ``public.outcomes``."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: SupabaseRestClient | Any | None = None,
    ):
        self.client = client or SupabaseRestClient(
            settings.supabase_url or "",
            settings.supabase_service_key or "",
            schema=settings.supabase_schema,
        )

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close:
            close()

    @staticmethod
    def _from_row(row: dict[str, Any]) -> OutcomeRecord:
        payload = dict(row)
        payload["ticker"] = payload.pop("symbol")
        return OutcomeRecord.model_validate(payload)

    @staticmethod
    def _to_row(record: OutcomeRecord) -> dict[str, Any]:
        payload = record.model_dump(mode="json")
        payload["symbol"] = payload.pop("ticker").upper()
        return payload

    def load(self, ticker: str, before: date | None = None) -> list[OutcomeRecord]:
        rows = self.client.select_all(
            "outcomes",
            {
                "symbol": f"eq.{ticker.upper()}",
                "select": "*",
                "order": "as_of_date.asc,horizon_days.asc",
            },
        )
        records = [self._from_row(row) for row in rows]
        # Keep the exact Python visibility rule as the canonical contract. This
        # also excludes unresolved rows when a dated analysis asks for memory.
        return sorted(
            [record for record in records if record.visible_on(before)],
            key=lambda record: (record.as_of_date, record.horizon_days),
        )

    def append(self, records: list[OutcomeRecord]) -> int:
        if not records:
            return 0
        by_symbol: dict[str, list[OutcomeRecord]] = {}
        for record in records:
            by_symbol.setdefault(record.ticker.upper(), []).append(record)

        written = 0
        for symbol, incoming in by_symbol.items():
            # Outcomes have a foreign key to tickers. The upsert is a no-op for
            # an existing symbol and gives direct backtest imports the same
            # behavior as the normal market-data pipeline.
            self.client.upsert("tickers", {"symbol": symbol}, on_conflict="symbol")
            existing_rows = self.client.select(
                "outcomes",
                {
                    "symbol": f"eq.{symbol}",
                    "select": "as_of_date,horizon_days,source",
                },
            )
            existing = {
                (row["as_of_date"], int(row["horizon_days"]), row["source"])
                for row in existing_rows
            }
            fresh: list[dict[str, Any]] = []
            for record in incoming:
                row = self._to_row(record)
                key = (row["as_of_date"], row["horizon_days"], row["source"])
                if key in existing:
                    continue
                existing.add(key)
                fresh.append(row)
            if fresh:
                self.client.upsert(
                    "outcomes",
                    fresh,
                    on_conflict="symbol,as_of_date,horizon_days,source",
                )
                written += len(fresh)
        return written

    def calibration(self, ticker: str, before: date | None = None) -> CalibrationSummary:
        return compute_calibration(ticker, self.load(ticker, before=before))

    def save_calibration(self, ticker: str) -> CalibrationSummary | None:
        """Return the derived summary without persisting a stale copy."""
        summary = self.calibration(ticker)
        return summary if summary.trials else None


def build_outcome_store(settings: Settings):
    if settings.storage_backend == "supabase":
        return SupabaseOutcomeStore(settings)

    from .outcomes import OutcomeStore

    return OutcomeStore(settings.data_dir)
