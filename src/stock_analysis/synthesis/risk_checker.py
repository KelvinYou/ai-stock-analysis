from __future__ import annotations

import math

from stock_analysis.models.market_data import TickerData
from stock_analysis.models.synthesis import Briefing, RiskAssessment


class RiskChecker:
    """Deterministic risk assessment — no LLM, pure computation."""

    def assess(self, ticker_data: TickerData, briefing: Briefing) -> RiskAssessment:
        volatility = self._compute_volatility(ticker_data)
        conviction_abs = abs(briefing.conviction.score)
        convergence = briefing.conviction.signal_convergence

        position_pct = self._suggest_position_size(conviction_abs, convergence, volatility)
        max_dd = self._estimate_max_drawdown(ticker_data, volatility)
        correlation_notes = self._check_correlations(ticker_data)

        risk_reward = None
        if briefing.conviction.score > 0 and volatility > 0:
            risk_reward = f"{round(conviction_abs / volatility, 2)}:1"
        elif briefing.conviction.score < 0:
            risk_reward = "N/A (bearish signal)"

        return RiskAssessment(
            position_size_suggestion=f"{position_pct}% of portfolio",
            correlation_notes=correlation_notes,
            max_drawdown_scenario=max_dd,
            risk_reward_ratio=risk_reward,
        )

    def _compute_volatility(self, ticker_data: TickerData) -> float:
        closes = [bar.close for bar in ticker_data.price_history]
        if len(closes) < 20:
            return 0.0
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
        ]
        recent = returns[-60:]  # ~3 months
        mean = sum(recent) / len(recent)
        variance = sum((r - mean) ** 2 for r in recent) / len(recent)
        daily_vol = math.sqrt(variance)
        annualized = daily_vol * math.sqrt(252)
        return round(annualized, 4)

    def _suggest_position_size(
        self, conviction: float, convergence: float, volatility: float
    ) -> float:
        # Base: 2% of portfolio
        # Scale up with conviction and convergence, down with volatility
        base = 2.0
        conviction_mult = 0.5 + conviction  # 0.5 to 1.5
        convergence_mult = 0.5 + (convergence * 0.5)  # 0.5 to 1.0
        vol_mult = max(0.3, 1.0 - volatility)  # higher vol = smaller position

        size = base * conviction_mult * convergence_mult * vol_mult
        return round(min(max(size, 0.5), 5.0), 1)  # clamp 0.5% - 5%

    def _estimate_max_drawdown(self, ticker_data: TickerData, volatility: float) -> str:
        closes = [bar.close for bar in ticker_data.price_history]
        if not closes:
            return "Insufficient data"

        # Historical max drawdown
        peak = closes[0]
        max_dd = 0.0
        for c in closes:
            if c > peak:
                peak = c
            dd = (peak - c) / peak
            if dd > max_dd:
                max_dd = dd

        current = closes[-1]
        projected_dd = round(volatility * 2 * 100, 1)  # 2-sigma move

        return (
            f"Historical max drawdown: {round(max_dd * 100, 1)}% over past year. "
            f"Projected worst case (2-sigma): ~{projected_dd}% from current ${current:.2f}."
        )

    def _check_correlations(self, ticker_data: TickerData) -> list[str]:
        notes = []
        sector = ticker_data.info.sector
        beta = ticker_data.info.beta

        if beta is not None:
            if beta > 1.3:
                notes.append(
                    f"High beta ({beta:.2f}) — amplifies market moves. "
                    "Consider reducing if portfolio is already tech/growth heavy."
                )
            elif beta < 0.7:
                notes.append(
                    f"Low beta ({beta:.2f}) — defensive characteristic. "
                    "Good for portfolio diversification."
                )

        if sector:
            notes.append(f"Sector: {sector} — check existing portfolio exposure to this sector.")

        return notes if notes else ["No significant correlation flags."]
