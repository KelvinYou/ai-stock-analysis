from __future__ import annotations

import math

from stock_analysis.data.technicals import compute_technicals
from stock_analysis.models.market_data import TechnicalSnapshot, TickerData
from stock_analysis.models.synthesis import ActionPlan, Briefing, RiskAssessment

# Below this conviction magnitude, the signal is too weak to quote precise
# levels — emit nulls with a "wait for clearer setup" note instead of
# manufactured precision.
_MIN_CONVICTION_FOR_LEVELS = 0.3
_MIN_CONVERGENCE_FOR_LEVELS = 0.4


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

    def plan_action(self, ticker_data: TickerData, briefing: Briefing) -> ActionPlan:
        """Translate the signal into concrete limit/stop/target prices.

        Bullish → buy-the-dip entry, ATR stop, two take-profit rungs.
        Bearish → no new entry; exit level at/near current + invalidation stop.
        Low conviction / divergent agents → no levels, just a wait note.
        """
        score = briefing.conviction.score
        convergence = briefing.conviction.signal_convergence

        if (
            abs(score) <= _MIN_CONVICTION_FOR_LEVELS
            or convergence < _MIN_CONVERGENCE_FOR_LEVELS
        ):
            return ActionPlan(
                note=(
                    "Signal too mixed for precise levels "
                    f"(conviction {score:+.2f}, convergence {convergence:.2f}). "
                    "Wait for a clearer setup."
                ),
            )

        snap = compute_technicals(ticker_data.info.symbol, ticker_data.price_history)
        close = snap.close
        atr = snap.atr_14 or (close * 0.02)  # fallback: 2% of price if ATR unavailable

        if score > 0:
            return self._plan_bullish(snap, close, atr)
        return self._plan_bearish(snap, close, atr)

    def _plan_bullish(self, snap: TechnicalSnapshot, close: float, atr: float) -> ActionPlan:
        # Entry: wait for a pullback to known support, otherwise slightly below current
        if snap.sma_20 and close > snap.sma_20:
            entry = round(snap.sma_20, 2)
            entry_why = f"Buy-the-dip to SMA-20 support near ${entry:.2f}"
        elif snap.bb_lower and close > snap.bb_lower:
            entry = round((close + snap.bb_lower) / 2, 2)
            entry_why = (
                f"Midway between current (${close:.2f}) and "
                f"Bollinger lower band (${snap.bb_lower:.2f})"
            )
        else:
            entry = round(close * 0.98, 2)
            entry_why = f"2% below current price (${close:.2f}) — no cleaner support above"

        stop = round(entry - 2 * atr, 2)
        stop_why = f"2x ATR-14 (${atr:.2f}) below entry — invalidates the setup"

        # TP1: nearest technical resistance above current price
        resistances = [r for r in (snap.sma_200, snap.bb_upper, snap.high_52w) if r and r > close]
        tp1 = round(min(resistances), 2) if resistances else round(close * 1.08, 2)

        # TP2: stretch target — 52w high or +15%, whichever is higher (and above TP1)
        tp2_candidates = [c for c in (snap.high_52w, close * 1.15) if c and c > tp1]
        tp2 = round(max(tp2_candidates), 2) if tp2_candidates else None

        target_why = (
            "TP1 = nearest technical resistance (SMA-200, BB-upper, or 52w high). "
            "TP2 = 52w high / +15% stretch. Consider scaling out: sell half at TP1, "
            "let the rest ride to TP2."
        )

        return ActionPlan(
            entry_limit=entry,
            entry_rationale=entry_why,
            stop_loss=stop,
            stop_rationale=stop_why,
            take_profit_1=tp1,
            take_profit_2=tp2,
            target_rationale=target_why,
        )

    def _plan_bearish(self, snap: TechnicalSnapshot, close: float, atr: float) -> ActionPlan:
        exit_now = round(close, 2)
        invalidation = round(close + 2 * atr, 2)
        supports = [s for s in (snap.sma_200, snap.bb_lower, snap.low_52w) if s and s < close]
        next_support = round(max(supports), 2) if supports else round(close * 0.92, 2)

        return ActionPlan(
            entry_limit=None,
            entry_rationale="Bearish signal — do not initiate new long positions.",
            stop_loss=invalidation,
            stop_rationale=(
                f"If still holding: exit if price breaks above ${invalidation:.2f} "
                f"(thesis invalidated)."
            ),
            take_profit_1=exit_now,
            take_profit_2=next_support,
            target_rationale=(
                f"Primary: reduce/exit at/near current ${exit_now:.2f}. "
                f"Next downside watch: ${next_support:.2f} (nearest support)."
            ),
        )
