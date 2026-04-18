from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.debate import DebateResult
from stock_analysis.models.market_data import TickerData
from stock_analysis.models.synthesis import Briefing

T = TypeVar("T", bound=BaseModel)


class DataStore:
    """JSON file storage: one directory per ticker per date."""

    def __init__(self, base_dir: str = "data"):
        self.base = Path(base_dir)

    def _ticker_dir(self, ticker: str, for_date: date | None = None) -> Path:
        d = for_date or date.today()
        path = self.base / ticker.upper() / d.isoformat()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _save(self, ticker: str, filename: str, model: BaseModel, for_date: date | None = None) -> Path:
        path = self._ticker_dir(ticker, for_date) / filename
        path.write_text(model.model_dump_json(indent=2))
        return path

    def _load(self, ticker: str, filename: str, model_cls: type[T], for_date: date | None = None) -> T | None:
        path = self._ticker_dir(ticker, for_date) / filename
        if not path.exists():
            return None
        return model_cls.model_validate_json(path.read_text())

    # --- Layer 1 ---
    def save_market_data(self, ticker: str, data: TickerData, for_date: date | None = None) -> Path:
        return self._save(ticker, "market_data.json", data, for_date)

    def load_market_data(self, ticker: str, for_date: date | None = None) -> TickerData | None:
        return self._load(ticker, "market_data.json", TickerData, for_date)

    # --- Layer 2 ---
    def save_analyst_reports(self, ticker: str, reports: AnalystReports, for_date: date | None = None) -> Path:
        return self._save(ticker, "analyst_reports.json", reports, for_date)

    def load_analyst_reports(self, ticker: str, for_date: date | None = None) -> AnalystReports | None:
        return self._load(ticker, "analyst_reports.json", AnalystReports, for_date)

    # --- Layer 3 ---
    def save_debate_result(self, ticker: str, result: DebateResult, for_date: date | None = None) -> Path:
        return self._save(ticker, "debate_result.json", result, for_date)

    def load_debate_result(self, ticker: str, for_date: date | None = None) -> DebateResult | None:
        return self._load(ticker, "debate_result.json", DebateResult, for_date)

    # --- Layer 4 ---
    def save_briefing(self, ticker: str, briefing: Briefing, for_date: date | None = None) -> Path:
        return self._save(ticker, "briefing.json", briefing, for_date)

    def load_briefing(self, ticker: str, for_date: date | None = None) -> Briefing | None:
        return self._load(ticker, "briefing.json", Briefing, for_date)
