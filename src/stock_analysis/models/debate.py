from __future__ import annotations

from pydantic import BaseModel, Field

from .agent_reports import Confidence, Signal


class DebateArgument(BaseModel):
    position: str  # "bull" or "bear"
    round_number: int
    argument: str
    key_points: list[str]
    rebuttal_to_previous: str | None = None


class DebateRound(BaseModel):
    round_number: int
    bull_argument: DebateArgument
    bear_argument: DebateArgument


class DebateResult(BaseModel):
    ticker: str
    rounds: list[DebateRound]
    bull_case_summary: str
    bear_case_summary: str
    key_points_of_agreement: list[str]
    key_points_of_disagreement: list[str]
    unresolved_uncertainties: list[str]


class ResearchVerdict(BaseModel):
    """Layer 3.5 adjudication of the bull/bear debate.

    The debate produces two advocacy pieces and no ruling, which left the
    synthesizer to both judge and summarize in one step. This separates the
    ruling out: which side carried the argument, what would prove it wrong, and
    what evidence is missing rather than merely contested.
    """

    ticker: str
    judged_view: Signal
    confidence: Confidence
    thesis: str
    winning_side: str  # "bull" | "bear" | "neither"
    strongest_counterexample: str
    invalidation_conditions: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    decisive_factors: list[str] = Field(default_factory=list)
