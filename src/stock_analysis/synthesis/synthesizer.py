from __future__ import annotations

import json
import logging

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from stock_analysis._query_retry import query_with_retry


def _extract_result(message: ResultMessage) -> dict | None:
    if message.structured_output:
        return message.structured_output
    if message.result:
        try:
            return json.loads(message.result)
        except json.JSONDecodeError:
            pass
    return None

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import AnalystReports, Signal
from stock_analysis.models.debate import DebateResult
from stock_analysis.models.market_data import TickerData
from stock_analysis.models.synthesis import Briefing, ConvictionScore

logger = logging.getLogger(__name__)

# Required sign of conviction.score for each signal. 0 = no constraint.
_SIGNAL_SIGN: dict[Signal, int] = {
    Signal.STRONG_BUY: +1,
    Signal.BUY: +1,
    Signal.NEUTRAL: 0,
    Signal.SELL: -1,
    Signal.STRONG_SELL: -1,
}


def _reconcile_conviction(signal: Signal, conviction: ConvictionScore) -> ConvictionScore:
    """Guarantee sign(conviction.score) matches the signal direction.

    The model occasionally emits e.g. `overall_signal=sell` with a positive
    conviction score. When that happens we preserve the magnitude (the model's
    stated confidence) but flip the sign so downstream math is coherent.
    """
    required = _SIGNAL_SIGN[signal]
    if required == 0:
        return conviction
    if (required > 0 and conviction.score >= 0) or (required < 0 and conviction.score <= 0):
        return conviction
    logger.warning(
        "Synthesizer sign mismatch: signal=%s score=%+.2f — flipping sign",
        signal.value,
        conviction.score,
    )
    return conviction.model_copy(update={"score": -conviction.score})

BRIEFING_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_signal": {
            "type": "string",
            "enum": ["strong_buy", "buy", "neutral", "sell", "strong_sell"],
        },
        "conviction": {
            "type": "object",
            "properties": {
                "score": {
                    "type": "number",
                    "description": "-1.0 (strong sell) to +1.0 (strong buy)",
                },
                "signal_convergence": {
                    "type": "number",
                    "description": "0.0 (agents disagree) to 1.0 (full agreement)",
                },
                "explanation": {"type": "string"},
            },
            "required": ["score", "signal_convergence", "explanation"],
        },
        "executive_summary": {
            "type": "string",
            "description": "2-3 paragraph synthesis of the full analysis",
        },
        "bull_case": {"type": "string"},
        "bear_case": {"type": "string"},
        "key_uncertainties": {
            "type": "array",
            "items": {"type": "string"},
        },
        "catalysts_upcoming": {
            "type": "array",
            "items": {"type": "string"},
        },
        "agent_signal_breakdown": {
            "type": "object",
            "description": "Map of agent name to signal value",
        },
    },
    "required": [
        "overall_signal",
        "conviction",
        "executive_summary",
        "bull_case",
        "bear_case",
        "key_uncertainties",
        "catalysts_upcoming",
        "agent_signal_breakdown",
    ],
}


class SynthesizerAgent:
    """Layer 4: Merges all analyst reports and debate into a final briefing."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.synthesis_model

    async def synthesize(
        self,
        ticker_data: TickerData,
        analyst_reports: AnalystReports,
        debate_result: DebateResult,
    ) -> Briefing:
        context = self._build_full_context(ticker_data, analyst_reports, debate_result)

        prompt = (
            f"{context}\n\n"
            "Synthesize all the above into a final investment briefing. "
            "Weigh the analyst reports and debate arguments to form your overall signal. "
            "Never default to 'neutral' — take a position while acknowledging uncertainty. "
            "The conviction score should reflect how strongly the signals converge.\n\n"
            "CRITICAL — score sign must match signal direction:\n"
            "  strong_buy/buy  → score in (0, 1]\n"
            "  neutral          → score near 0 (roughly [-0.1, 0.1])\n"
            "  sell/strong_sell → score in [-1, 0)\n"
            "A sell with a positive score is invalid output."
        )

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=(
                "You are a senior investment strategist producing a final briefing. "
                "You have access to fundamental, technical, sentiment, and macro analyses, "
                "plus a bull/bear adversarial debate. Synthesize everything into an actionable, "
                "balanced briefing. Be direct and specific."
            ),
            permission_mode="bypassPermissions",
            output_format={"type": "json_schema", "schema": BRIEFING_OUTPUT_SCHEMA},
            max_turns=3,
        )

        message = await query_with_retry(
            prompt=prompt, options=options, label="synthesis"
        )
        result = _extract_result(message)

        if result is None:
            raise RuntimeError("Synthesis agent failed to produce output")

        from datetime import date

        from stock_analysis.models.synthesis import RiskAssessment

        signal = Signal(result["overall_signal"])
        conviction = _reconcile_conviction(signal, ConvictionScore(**result["conviction"]))

        return Briefing(
            ticker=ticker_data.info.symbol,
            date=date.today().isoformat(),
            overall_signal=signal,
            conviction=conviction,
            executive_summary=result["executive_summary"],
            bull_case=result["bull_case"],
            bear_case=result["bear_case"],
            key_uncertainties=result["key_uncertainties"],
            catalysts_upcoming=result["catalysts_upcoming"],
            risk_assessment=RiskAssessment(
                position_size_suggestion="pending",
                correlation_notes=[],
                max_drawdown_scenario="pending",
            ),
            agent_signal_breakdown=result["agent_signal_breakdown"],
        )

    def _build_full_context(
        self,
        ticker_data: TickerData,
        analyst_reports: AnalystReports,
        debate_result: DebateResult,
    ) -> str:
        info = ticker_data.info
        sections = [
            f"# Full Analysis: {info.symbol} — {info.name}",
            f"Sector: {info.sector} | Industry: {info.industry}",
            f"Market Cap: {info.market_cap} | P/E: {info.pe_ratio} | Beta: {info.beta}",
            "",
            "---",
            "",
            "## Fundamentals Report",
            f"Signal: **{analyst_reports.fundamentals.signal.value}** (Confidence: {analyst_reports.fundamentals.confidence.value})",
            f"P/E: {analyst_reports.fundamentals.pe_assessment}",
            f"Margins: {analyst_reports.fundamentals.margin_analysis}",
            f"Debt: {analyst_reports.fundamentals.debt_analysis}",
            f"Growth: {analyst_reports.fundamentals.growth_outlook}",
            f"Summary: {analyst_reports.fundamentals.summary}",
            "",
            "## Sentiment Report",
            f"Signal: **{analyst_reports.sentiment.signal.value}** (Confidence: {analyst_reports.sentiment.confidence.value})",
            f"News tone: {analyst_reports.sentiment.news_tone}",
            f"Themes: {', '.join(analyst_reports.sentiment.key_themes)}",
            f"Summary: {analyst_reports.sentiment.summary}",
            "",
            "## Technical Report",
            f"Signal: **{analyst_reports.technical.signal.value}** (Confidence: {analyst_reports.technical.confidence.value})",
            f"Trend: {analyst_reports.technical.trend}",
            f"RSI-14: {analyst_reports.technical.rsi_14}",
            f"Summary: {analyst_reports.technical.summary}",
            "",
            "## Macro / FX Report",
            f"Signal: **{analyst_reports.macro.signal.value}** (Confidence: {analyst_reports.macro.confidence.value})",
            f"Fed impact: {analyst_reports.macro.fed_impact}",
            f"Summary: {analyst_reports.macro.summary}",
            "",
            "---",
            "",
            "## Adversarial Debate",
        ]

        for r in debate_result.rounds:
            sections.append(f"\n### Round {r.round_number}")
            sections.append(f"**BULL:** {r.bull_argument.argument}")
            sections.append(f"**BEAR:** {r.bear_argument.argument}")

        sections.extend([
            "",
            f"**Bull case summary:** {debate_result.bull_case_summary}",
            f"**Bear case summary:** {debate_result.bear_case_summary}",
            f"**Points of agreement:** {', '.join(debate_result.key_points_of_agreement)}",
            f"**Points of disagreement:** {', '.join(debate_result.key_points_of_disagreement)}",
            f"**Unresolved:** {', '.join(debate_result.unresolved_uncertainties)}",
        ])

        return "\n".join(sections)
