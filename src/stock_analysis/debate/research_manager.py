"""Layer 3.5 — Research Manager: rules on the debate instead of summarizing it.

The debate produces two advocacy pieces plus a neutral summary, and previously
handed all of it straight to the synthesizer, which then had to judge the
argument and write the briefing in one step. Those are different jobs: judging
asks "who was right and what would prove them wrong", writing asks "what should
the reader do". Merging them is why forced-direction pressure landed on the
synthesizer in the first place.

What this layer adds that a summary cannot:

- an explicit ruling (`winning_side`, `judged_view`) that can be compared
  against the analysts' mechanical consensus, so disagreement becomes visible
  instead of averaged away
- the single strongest counterexample to the winning case, kept intact rather
  than diluted into a list of risks
- falsifiable `invalidation_conditions` — what would have to happen for the
  thesis to be wrong — which is what Layer 6 later scores the thesis against
- `evidence_gaps`: what is *missing* rather than merely contested, which the
  bull/bear framing structurally cannot surface because neither advocate
  benefits from naming it

The verdict is advisory. It informs the synthesizer's prose and is persisted for
review, but it does not move `signal_convergence` — that stays a deterministic
function of the analyst reports, so no LLM layer can inflate it.
"""

from __future__ import annotations

import json
import logging

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from stock_analysis._query_retry import query_with_retry
from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import AnalystReports, Confidence, Signal
from stock_analysis.models.debate import DebateResult, ResearchVerdict
from stock_analysis.models.market_data import TickerData

logger = logging.getLogger(__name__)

RESEARCH_MANAGER_SYSTEM = (
    "You are a research manager adjudicating a bull/bear investment debate. "
    "You are not an advocate and you are not a summarizer — you rule.\n\n"
    "Guidelines:\n"
    "- Decide which side actually carried the argument on evidence, not on tone "
    "or volume of points\n"
    "- 'neither' is a legitimate ruling when both cases rest on the same "
    "unresolved unknown\n"
    "- State the single strongest counterexample to your own ruling, in full "
    "force — do not soften it\n"
    "- Write invalidation conditions as observable events with thresholds "
    "('gross margin below 40% for two consecutive quarters'), not as vague "
    "risks ('margins could compress')\n"
    "- Separate evidence GAPS (data nobody has) from evidence DISPUTES (data "
    "both sides read differently); only the former belong in evidence_gaps\n"
    "- If the debate rests on macro facts the analysts flagged as unavailable, "
    "say so in evidence_gaps and lower your confidence accordingly"
)

VERDICT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "judged_view": {
            "type": "string",
            "enum": ["strong_buy", "buy", "neutral", "sell", "strong_sell"],
            "description": "Your ruling on direction. neutral is valid.",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Your confidence in the ruling, not in the stock",
        },
        "winning_side": {
            "type": "string",
            "enum": ["bull", "bear", "neither"],
        },
        "thesis": {
            "type": "string",
            "description": "The load-bearing claim, in 2-4 sentences",
        },
        "strongest_counterexample": {
            "type": "string",
            "description": "The best argument against your own ruling, stated at full strength",
        },
        "invalidation_conditions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observable events with thresholds that would falsify the thesis",
        },
        "evidence_gaps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Data nobody in the debate had (not merely disputed data)",
        },
        "decisive_factors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The facts that actually decided the ruling",
        },
    },
    "required": [
        "judged_view",
        "confidence",
        "winning_side",
        "thesis",
        "strongest_counterexample",
        "invalidation_conditions",
        "evidence_gaps",
        "decisive_factors",
    ],
}


def _extract_result(message: ResultMessage) -> dict | None:
    if message.structured_output:
        return message.structured_output
    if message.result:
        try:
            return json.loads(message.result)
        except json.JSONDecodeError:
            pass
    return None


class ResearchManager:
    """Adjudicates the debate into a single falsifiable verdict."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.research_manager_model

    async def adjudicate(
        self,
        ticker_data: TickerData,
        analyst_reports: AnalystReports,
        debate_result: DebateResult,
    ) -> ResearchVerdict:
        prompt = self._build_prompt(ticker_data, analyst_reports, debate_result)

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=RESEARCH_MANAGER_SYSTEM,
            permission_mode="bypassPermissions",
            output_format={"type": "json_schema", "schema": VERDICT_OUTPUT_SCHEMA},
            max_turns=3,
        )

        message = await query_with_retry(
            prompt=prompt, options=options, label="research-manager"
        )
        result = _extract_result(message)
        if result is None:
            raise RuntimeError("Research manager failed to produce a verdict")

        return ResearchVerdict(
            ticker=ticker_data.info.symbol,
            judged_view=Signal(result["judged_view"]),
            confidence=Confidence(result["confidence"]),
            thesis=result["thesis"],
            winning_side=result["winning_side"],
            strongest_counterexample=result["strongest_counterexample"],
            invalidation_conditions=result.get("invalidation_conditions") or [],
            evidence_gaps=result.get("evidence_gaps") or [],
            decisive_factors=result.get("decisive_factors") or [],
        )

    def _build_prompt(
        self,
        ticker_data: TickerData,
        analyst_reports: AnalystReports,
        debate_result: DebateResult,
    ) -> str:
        info = ticker_data.info
        sections = [
            f"# Debate to adjudicate: {info.symbol} — {info.name}",
            f"Sector: {info.sector} | Industry: {info.industry} | Beta: {info.beta}",
            "",
            "## Analyst signals (independent of the debate)",
        ]
        for label, report in (
            ("Fundamentals", analyst_reports.fundamentals),
            ("Sentiment", analyst_reports.sentiment),
            ("Technical", analyst_reports.technical),
            ("Macro / FX", analyst_reports.macro),
        ):
            sections.append(
                f"- {label}: **{report.signal.value}** "
                f"(confidence {report.confidence.value}) — {report.summary}"
            )

        sections.extend(["", "## Debate rounds"])
        for round_ in debate_result.rounds:
            sections.append(f"\n### Round {round_.round_number}")
            sections.append(f"**BULL:** {round_.bull_argument.argument}")
            sections.append(f"**BEAR:** {round_.bear_argument.argument}")

        sections.extend(
            [
                "",
                f"**Bull summary:** {debate_result.bull_case_summary}",
                f"**Bear summary:** {debate_result.bear_case_summary}",
                f"**Agreed:** {'; '.join(debate_result.key_points_of_agreement)}",
                f"**Disputed:** {'; '.join(debate_result.key_points_of_disagreement)}",
                f"**Unresolved:** {'; '.join(debate_result.unresolved_uncertainties)}",
                "",
                ("Rule on this debate. Which side carried it on evidence, what is the "
                "load-bearing thesis, what is the strongest case against your ruling, "
                "and what observable events would falsify the thesis?"),
            ]
        )
        return "\n".join(sections)
