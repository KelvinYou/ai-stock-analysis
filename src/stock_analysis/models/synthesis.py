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


class ActionPlan(BaseModel):
    """Concrete order levels so a user can place limit orders with their broker.

    All price fields are nullable. When conviction is too low to justify precise
    levels, prices are None and `note` explains why.
    """

    entry_limit: float | None = None
    entry_rationale: str | None = None
    stop_loss: float | None = None
    stop_rationale: str | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    target_rationale: str | None = None
    horizon: str = "swing (2-8 weeks)"
    note: str | None = None


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
    action_plan: ActionPlan | None = None
    agent_signal_breakdown: dict[str, str]

    @field_validator("agent_signal_breakdown", mode="before")
    @classmethod
    def coerce_signal_values(cls, v: Any) -> dict[str, str]:
        if isinstance(v, dict):
            return {k: str(val) for k, val in v.items()}
        return v
