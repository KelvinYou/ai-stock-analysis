from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from .agent_reports import Signal


class ConvictionScore(BaseModel):
    score: float  # -1.0 (strong sell) to +1.0 (strong buy)
    signal_convergence: float  # 0.0 (agents disagree) to 1.0 (full agreement)
    explanation: str


class RiskAssessment(BaseModel):
    position_size_suggestion: str
    correlation_notes: list[str]
    max_drawdown_scenario: str
    risk_reward_ratio: str | None = None


class Briefing(BaseModel):
    ticker: str
    date: str
    overall_signal: Signal
    conviction: ConvictionScore
    executive_summary: str
    bull_case: str
    bear_case: str
    key_uncertainties: list[str]
    catalysts_upcoming: list[str]
    risk_assessment: RiskAssessment
    agent_signal_breakdown: dict[str, str]

    @field_validator("agent_signal_breakdown", mode="before")
    @classmethod
    def coerce_signal_values(cls, v: Any) -> dict[str, str]:
        if isinstance(v, dict):
            return {k: str(val) for k, val in v.items()}
        return v
