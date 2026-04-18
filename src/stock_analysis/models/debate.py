from __future__ import annotations

from pydantic import BaseModel


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
