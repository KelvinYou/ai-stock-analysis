from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .agent_reports import Signal
from .debate import ResearchVerdict


class TradeDecision(str, Enum):
    """Whether to act on the research view — separate from what the view is.

    A `neutral` research view paired with `watch` is a correct, complete result,
    not a failed analysis. Keeping the two axes apart is what lets the research
    layer stay honest while the execution layer stays conservative.
    """

    APPROVE = "approve"
    WATCH = "watch"
    REDUCE = "reduce"
    REJECT = "reject"


class ConvictionScore(BaseModel):
    score: float = Field(ge=-1.0, le=1.0)  # -1.0 (strong sell) to +1.0 (strong buy)
    signal_convergence: float = Field(ge=0.0, le=1.0)  # 0.0 (disagree) to 1.0 (agreement)
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


class PositionSizing(BaseModel):
    """Size derived from stop distance and a risk budget, not from conviction alone.

    The old path multiplied conviction/convergence/volatility into a percentage,
    which produced a number with no stated meaning. Here the meaning is fixed:
    if the stop is hit, the loss is `risk_budget_pct` of the equity sleeve.
    """

    risk_budget_pct: float | None = None
    risk_budget_source: str
    stop_distance_pct: float | None = None
    suggested_position_pct: float | None = None
    capped_by: str | None = None
    notes: list[str] = Field(default_factory=list)


class ExposureStatus(str, Enum):
    WITHIN_CAP = "within_cap"
    BREACH = "breach"
    CAP_UNCONFIGURED = "cap_unconfigured"
    HOLDINGS_UNAVAILABLE = "holdings_unavailable"


class ExposureCheck(BaseModel):
    """One concentration check against a policy cap.

    `CAP_UNCONFIGURED` is deliberately distinct from `WITHIN_CAP`: an unset
    policy cap means the check could not be performed, never that it passed.
    """

    label: str
    current_pct: float | None = None
    projected_pct: float | None = None
    cap_pct: float | None = None
    status: ExposureStatus
    detail: str


class PortfolioGateResult(BaseModel):
    """Layer 5 output: whether this single-name idea survives portfolio context."""

    decision: TradeDecision
    reasons: list[str]
    sizing: PositionSizing
    exposures: list[ExposureCheck] = Field(default_factory=list)
    holdings_source: str
    policy_source: str
    equity_sleeve_value: float | None = None
    valuation_currency: str | None = None
    already_held: bool = False
    held_shares: float | None = None


class Briefing(BaseModel):
    ticker: str
    date: str
    overall_signal: Signal
    # The research layer's honest directional judgment. `overall_signal` is kept
    # as the same value for existing consumers (web, scorer, portfolio sim);
    # `trade_decision` is the separate "should we act on it" axis.
    research_view: Signal | None = None
    trade_decision: TradeDecision | None = None
    conviction: ConvictionScore
    executive_summary: str
    bull_case: str
    bear_case: str
    key_uncertainties: list[str]
    catalysts_upcoming: list[str]
    risk_assessment: RiskAssessment
    action_plan: ActionPlan | None = None
    research_verdict: ResearchVerdict | None = None
    portfolio_gate: PortfolioGateResult | None = None
    agent_signal_breakdown: dict[str, str]

    @field_validator("agent_signal_breakdown", mode="before")
    @classmethod
    def coerce_signal_values(cls, v: Any) -> dict[str, str]:
        if isinstance(v, dict):
            return {k: str(val) for k, val in v.items()}
        return v
