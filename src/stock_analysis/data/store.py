from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.debate import DebateResult
from stock_analysis.models.market_data import PriceBar, TechnicalSnapshot, TickerData
from stock_analysis.models.synthesis import Briefing

T = TypeVar("T", bound=BaseModel)


class DataStore:
    """Per-ticker flat storage: price_history.csv + JSON snapshots, overwritten daily.

    Layout:
        data/AAPL/
            price_history.csv       # full OHLCV history, overwritten on each fetch
            fundamentals.json       # TickerInfo + financials + news snapshot
            analyst_reports.json
            debate_result.json
            briefing.json

    Backtest paths (for_date set) fall back to the legacy per-date subdirectory layout:
        data/AAPL/2026-04-18/market_data.json
    """

    def __init__(self, base_dir: str = "data"):
        self.base = Path(base_dir)

    def _flat_dir(self, ticker: str) -> Path:
        path = self.base / ticker.upper()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _dated_dir(self, ticker: str, for_date: date) -> Path:
        path = self.base / ticker.upper() / for_date.isoformat()
        path.mkdir(parents=True, exist_ok=True)
        return path

    # --- Layer 1 ---

    def save_market_data(self, ticker: str, data: TickerData) -> Path:
        d = self._flat_dir(ticker)

        csv_path = d / "price_history.csv"
        with csv_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "open", "high", "low", "close", "volume"])
            for bar in data.price_history:
                writer.writerow([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])

        fund_dict = json.loads(data.model_dump_json())
        del fund_dict["price_history"]
        (d / "fundamentals.json").write_text(json.dumps(fund_dict, indent=2))

        return csv_path

    def last_price_bar_date(self, ticker: str) -> date | None:
        """Return the most recent bar date in price_history.csv, or None if absent."""
        csv_path = self.base / ticker.upper() / "price_history.csv"
        if not csv_path.exists():
            return None
        last: str | None = None
        with csv_path.open() as f:
            for row in csv.DictReader(f):
                last = row["date"]
        if last is None:
            return None
        return date.fromisoformat(last)

    def merge_market_data(self, ticker: str, data: TickerData) -> list[PriceBar]:
        """Merge new bars into the on-disk CSV (dedup by date; newer wins).

        Always overwrites fundamentals.json with the latest snapshot.
        Returns the full merged price history so callers can feed downstream
        consumers (e.g. technicals) without a second read.
        """
        d = self._flat_dir(ticker)
        csv_path = d / "price_history.csv"

        bars_by_date: dict[date, PriceBar] = {}
        if csv_path.exists():
            with csv_path.open() as f:
                for row in csv.DictReader(f):
                    bd = date.fromisoformat(row["date"])
                    bars_by_date[bd] = PriceBar(
                        date=bd,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(row["volume"]),
                    )
        for bar in data.price_history:
            bars_by_date[bar.date] = bar

        merged = sorted(bars_by_date.values(), key=lambda b: b.date)

        with csv_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "open", "high", "low", "close", "volume"])
            for bar in merged:
                writer.writerow([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])

        fund_dict = json.loads(data.model_dump_json())
        del fund_dict["price_history"]
        (d / "fundamentals.json").write_text(json.dumps(fund_dict, indent=2))

        return merged

    def load_market_data(self, ticker: str) -> TickerData | None:
        d = self.base / ticker.upper()
        csv_path = d / "price_history.csv"
        fund_path = d / "fundamentals.json"
        if not csv_path.exists() or not fund_path.exists():
            return None

        bars: list[PriceBar] = []
        with csv_path.open() as f:
            for row in csv.DictReader(f):
                bars.append(PriceBar(
                    date=row["date"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]),
                ))

        fund_dict = json.loads(fund_path.read_text())
        fund_dict["price_history"] = [json.loads(b.model_dump_json()) for b in bars]
        return TickerData.model_validate(fund_dict)

    # --- Technicals (computed, no LLM) ---

    def save_technicals(self, ticker: str, snapshot: TechnicalSnapshot) -> Path:
        path = self._flat_dir(ticker) / "technicals.json"
        path.write_text(snapshot.model_dump_json(indent=2))
        return path

    def load_technicals(self, ticker: str) -> TechnicalSnapshot | None:
        path = self.base / ticker.upper() / "technicals.json"
        if not path.exists():
            return None
        return TechnicalSnapshot.model_validate_json(path.read_text())

    # --- Layer 2 ---

    def save_analyst_reports(self, ticker: str, reports: AnalystReports, for_date: date | None = None) -> Path:
        d = self._dated_dir(ticker, for_date) if for_date else self._flat_dir(ticker)
        path = d / "analyst_reports.json"
        path.write_text(reports.model_dump_json(indent=2))
        return path

    def load_analyst_reports(self, ticker: str, for_date: date | None = None) -> AnalystReports | None:
        d = (self.base / ticker.upper() / for_date.isoformat()) if for_date else (self.base / ticker.upper())
        path = d / "analyst_reports.json"
        if not path.exists():
            return None
        return AnalystReports.model_validate_json(path.read_text())

    # --- Layer 3 ---

    def save_debate_result(self, ticker: str, result: DebateResult, for_date: date | None = None) -> Path:
        d = self._dated_dir(ticker, for_date) if for_date else self._flat_dir(ticker)
        path = d / "debate_result.json"
        path.write_text(result.model_dump_json(indent=2))
        return path

    def load_debate_result(self, ticker: str, for_date: date | None = None) -> DebateResult | None:
        d = (self.base / ticker.upper() / for_date.isoformat()) if for_date else (self.base / ticker.upper())
        path = d / "debate_result.json"
        if not path.exists():
            return None
        return DebateResult.model_validate_json(path.read_text())

    # --- Layer 4 ---

    def save_briefing(self, ticker: str, briefing: Briefing, for_date: date | None = None) -> Path:
        d = self._dated_dir(ticker, for_date) if for_date else self._flat_dir(ticker)
        path = d / "briefing.json"
        path.write_text(briefing.model_dump_json(indent=2))
        return path

    def load_briefing(self, ticker: str, for_date: date | None = None) -> Briefing | None:
        d = (self.base / ticker.upper() / for_date.isoformat()) if for_date else (self.base / ticker.upper())
        path = d / "briefing.json"
        if not path.exists():
            return None
        return Briefing.model_validate_json(path.read_text())
