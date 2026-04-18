from __future__ import annotations

import json

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from stock_analysis._query_retry import query_with_retry


def _extract_result(message: ResultMessage) -> dict | None:
    """Extract structured output or parse JSON from result text."""
    if message.structured_output:
        return message.structured_output
    if message.result:
        try:
            return json.loads(message.result)
        except json.JSONDecodeError:
            pass
    return None

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.debate import DebateArgument, DebateResult, DebateRound
from stock_analysis.models.market_data import TickerData

BULL_SYSTEM = (
    "You are an optimistic equity researcher building the strongest possible investment case. "
    "Your job is to argue FOR buying this stock.\n\n"
    "Guidelines:\n"
    "- Highlight catalysts, growth drivers, and upside scenarios\n"
    "- Acknowledge risks only to explain why they are manageable or priced in\n"
    "- When rebutting the bear case, be specific — cite data from the analyst reports\n"
    "- Do not be blindly bullish — your credibility comes from acknowledging reality while "
    "making a compelling case\n"
    "- Structure your response as a clear argument with key points"
)

BEAR_SYSTEM = (
    "You are a skeptical equity researcher identifying every risk and reason NOT to buy. "
    "Your job is to argue AGAINST buying this stock.\n\n"
    "Guidelines:\n"
    "- Identify overvaluation, headwinds, competitive threats, and downside scenarios\n"
    "- Acknowledge strengths only to explain why they are already priced in or unsustainable\n"
    "- When rebutting the bull case, be specific — cite data from the analyst reports\n"
    "- Do not be blindly bearish — your credibility comes from rigorous risk analysis\n"
    "- Structure your response as a clear argument with key points"
)

ARGUMENT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "argument": {
            "type": "string",
            "description": "Your substantive argument (2-3 paragraphs)",
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 key bullet points",
        },
        "rebuttal_to_previous": {
            "type": ["string", "null"],
            "description": "Direct rebuttal to opponent's last argument (null if first round)",
        },
    },
    "required": ["argument", "key_points", "rebuttal_to_previous"],
}

SUMMARY_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "bull_case_summary": {"type": "string"},
        "bear_case_summary": {"type": "string"},
        "key_points_of_agreement": {
            "type": "array",
            "items": {"type": "string"},
        },
        "key_points_of_disagreement": {
            "type": "array",
            "items": {"type": "string"},
        },
        "unresolved_uncertainties": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "bull_case_summary",
        "bear_case_summary",
        "key_points_of_agreement",
        "key_points_of_disagreement",
        "unresolved_uncertainties",
    ],
}


class DebateEngine:
    """Layer 3: Adversarial debate between bull and bear researchers."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.deep_think_model
        self.rounds = s.debate_rounds

    async def run(
        self, ticker_data: TickerData, analyst_reports: AnalystReports
    ) -> DebateResult:
        context = self._build_context(ticker_data, analyst_reports)
        rounds: list[DebateRound] = []
        bull_args: list[DebateArgument] = []
        bear_args: list[DebateArgument] = []

        for round_num in range(1, self.rounds + 1):
            # Bull argues
            bull_arg = await self._get_argument(
                position="bull",
                round_number=round_num,
                context=context,
                own_args=bull_args,
                opponent_args=bear_args,
            )
            bull_args.append(bull_arg)

            # Bear rebuts
            bear_arg = await self._get_argument(
                position="bear",
                round_number=round_num,
                context=context,
                own_args=bear_args,
                opponent_args=bull_args,  # includes this round's bull argument
            )
            bear_args.append(bear_arg)

            rounds.append(
                DebateRound(
                    round_number=round_num,
                    bull_argument=bull_arg,
                    bear_argument=bear_arg,
                )
            )

        summary = await self._summarize(ticker_data.info.symbol, context, rounds)

        return DebateResult(
            ticker=ticker_data.info.symbol,
            rounds=rounds,
            **summary,
        )

    async def _get_argument(
        self,
        position: str,
        round_number: int,
        context: str,
        own_args: list[DebateArgument],
        opponent_args: list[DebateArgument],
    ) -> DebateArgument:
        system = BULL_SYSTEM if position == "bull" else BEAR_SYSTEM
        opponent = "bear" if position == "bull" else "bull"

        history = ""
        if own_args or opponent_args:
            history = "\n\n## Previous Debate Rounds\n"
            all_args = sorted(
                [(a, "bull") for a in own_args if position == "bull"]
                + [(a, "bear") for a in own_args if position == "bear"]
                + [(a, opponent) for a in opponent_args],
                key=lambda x: x[0].round_number,
            )
            for arg, side in all_args:
                history += f"\n### Round {arg.round_number} — {side.upper()}\n{arg.argument}\n"

        prompt = (
            f"## Analyst Reports Context\n{context}\n"
            f"{history}\n\n"
            f"This is round {round_number} of {self.rounds}. "
            f"Present your {position} argument."
        )
        if round_number > 1:
            prompt += f" Directly address the {opponent}'s previous points."

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=system,
            permission_mode="bypassPermissions",
            output_format={"type": "json_schema", "schema": ARGUMENT_OUTPUT_SCHEMA},
            max_turns=3,
        )

        message = await query_with_retry(
            prompt=prompt, options=options, label=f"debate-{position}-r{round_number}"
        )
        result = _extract_result(message)

        if result is None:
            raise RuntimeError(f"{position} researcher failed in round {round_number}")

        return DebateArgument(
            position=position,
            round_number=round_number,
            argument=result["argument"],
            key_points=result["key_points"],
            rebuttal_to_previous=result.get("rebuttal_to_previous"),
        )

    async def _summarize(
        self, ticker: str, context: str, rounds: list[DebateRound]
    ) -> dict:
        debate_text = ""
        for r in rounds:
            debate_text += f"\n## Round {r.round_number}\n"
            debate_text += f"**BULL:** {r.bull_argument.argument}\n"
            debate_text += f"**BEAR:** {r.bear_argument.argument}\n"

        prompt = (
            f"## Context\n{context}\n\n"
            f"## Full Debate\n{debate_text}\n\n"
            "Summarize this debate. Identify where the bull and bear agree, "
            "where they disagree, and what remains genuinely uncertain."
        )

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt="You are a neutral debate moderator summarizing an investment debate.",
            permission_mode="bypassPermissions",
            output_format={"type": "json_schema", "schema": SUMMARY_OUTPUT_SCHEMA},
            max_turns=3,
        )

        message = await query_with_retry(
            prompt=prompt, options=options, label="debate-summary"
        )
        result = _extract_result(message)

        if result is None:
            raise RuntimeError("Debate summary failed")

        return result

    def _build_context(
        self, ticker_data: TickerData, analyst_reports: AnalystReports
    ) -> str:
        info = ticker_data.info
        sections = [
            f"# {info.symbol} — {info.name}",
            f"Sector: {info.sector} | Industry: {info.industry} | Market Cap: {info.market_cap}",
            f"Current P/E: {info.pe_ratio} | Forward P/E: {info.forward_pe} | Beta: {info.beta}",
            "",
            f"## Fundamentals Analysis\n{analyst_reports.fundamentals.summary}",
            f"Signal: {analyst_reports.fundamentals.signal.value} | Confidence: {analyst_reports.fundamentals.confidence.value}",
            "",
            f"## Sentiment Analysis\n{analyst_reports.sentiment.summary}",
            f"Signal: {analyst_reports.sentiment.signal.value} | Confidence: {analyst_reports.sentiment.confidence.value}",
            "",
            f"## Technical Analysis\n{analyst_reports.technical.summary}",
            f"Signal: {analyst_reports.technical.signal.value} | Confidence: {analyst_reports.technical.confidence.value}",
            "",
            f"## Macro / FX Analysis\n{analyst_reports.macro.summary}",
            f"Signal: {analyst_reports.macro.signal.value} | Confidence: {analyst_reports.macro.confidence.value}",
        ]
        return "\n".join(sections)
