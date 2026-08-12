"""Layer 5 — portfolio risk gate. Deterministic, no LLM.

The chain this implements, in order:

    risk budget -> stop distance -> position size -> exposure caps -> decision

Each step's output is the next step's input, so the resulting percentage has a
stated meaning: *if the stop is hit, the loss is `risk_budget_pct` of the priced
equity sleeve*. The previous sizing formula multiplied conviction, convergence
and volatility together, which produced a percentage nothing could falsify.

The gate answers a different question from the rest of the pipeline. Layers 1-4
ask "is this a good idea"; this layer asks "is this a good idea *given what is
already owned*" — which is the only question that can be answered wrongly by an
otherwise perfect analysis.

Failure modes are all explicit and all conservative:

- no holdings file (public clone, or private submodule not checked out) -> WATCH
- policy cap is null -> the check reports CAP_UNCONFIGURED and the decision
  degrades to WATCH; it never substitutes a default cap
- no usable stop distance -> no size, and WATCH
"""

from __future__ import annotations

import logging
from pathlib import Path

from stock_analysis.models.market_data import TickerData
from stock_analysis.models.synthesis import (
    ActionPlan,
    Briefing,
    ExposureCheck,
    ExposureStatus,
    PortfolioGateResult,
    PositionSizing,
    TradeDecision,
)

from .holdings import (
    ConcentrationPolicy,
    HoldingsSnapshot,
    load_concentration_policy,
    load_holdings,
)
from .risk_checker import is_actionable

logger = logging.getLogger(__name__)

# Percent of the priced equity sleeve lost if the stop is hit. This is a
# repo-level convention, not a user policy target — `policy.yaml` has no
# per-trade risk key — so it is labelled as an assumption in the output rather
# than presented as the user's own setting.
DEFAULT_RISK_BUDGET_PCT = 0.5

_RISK_BUDGET_SOURCE = (
    f"repo default ({DEFAULT_RISK_BUDGET_PCT}% of priced equity sleeve per trade) — "
    "an assumption, not a policy.yaml target"
)

# Even a tight stop should not produce an unbounded position. This bound is a
# sanity rail on the arithmetic, and when it binds the output says so.
_MAX_POSITION_PCT = 25.0
_MIN_POSITION_PCT = 0.1

# Minimum reward:risk before a setup is worth taking. `RiskChecker._plan_bullish`
# picks TP1 as the nearest resistance above the *current* price while entry is a
# pullback to SMA-20, so TP1 can legitimately land just above — or below — the
# entry. That yields setups risking several dollars to make cents, which the old
# conviction-based sizing had no way to notice.
_MIN_REWARD_TO_RISK = 1.0


class PortfolioGate:
    """Decides APPROVE / WATCH / REDUCE / REJECT for one single-name idea."""

    def __init__(
        self,
        data_dir: str | Path = "data",
        risk_budget_pct: float = DEFAULT_RISK_BUDGET_PCT,
        holdings: HoldingsSnapshot | None = None,
        policy: ConcentrationPolicy | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.risk_budget_pct = risk_budget_pct
        self._holdings = holdings
        self._policy = policy

    # ------------------------------------------------------------------
    # loading

    def holdings(self) -> HoldingsSnapshot:
        if self._holdings is None:
            self._holdings = load_holdings(self.data_dir)
        return self._holdings

    def policy(self) -> ConcentrationPolicy:
        if self._policy is None:
            self._policy = load_concentration_policy()
        return self._policy

    # ------------------------------------------------------------------
    # public entry point

    def evaluate(self, ticker_data: TickerData, briefing: Briefing) -> PortfolioGateResult:
        holdings = self.holdings()
        policy = self.policy()
        plan = briefing.action_plan
        score = briefing.conviction.score
        convergence = briefing.conviction.signal_convergence

        held = holdings.find(ticker_data.info.symbol) if holdings.available else None
        sizing = self._size(plan, holdings)

        reasons: list[str] = []
        exposures: list[ExposureCheck] = []

        # --- direction first: a bearish or unactionable view needs no sizing ---
        if not is_actionable(score, convergence):
            reasons.append(
                f"Research view is not actionable (conviction {score:+.2f}, "
                f"convergence {convergence:.2f}) — no position to size."
            )
            return self._result(
                TradeDecision.WATCH, reasons, sizing, exposures, holdings, policy, held
            )

        if score < 0:
            if held is not None:
                reasons.append(
                    f"Bearish view on an existing position ({held.shares:g} shares) — "
                    "reduce or exit rather than hold through the thesis."
                )
                decision = TradeDecision.REDUCE
            else:
                reasons.append("Bearish view and no existing position — no long to open.")
                decision = TradeDecision.REJECT
            return self._result(
                decision, reasons, sizing, exposures, holdings, policy, held
            )

        # --- bullish path: size must exist before exposure means anything ---
        if sizing.suggested_position_pct is None:
            reasons.append(
                "No usable stop distance, so risk-based sizing is undefined — "
                "cannot approve a position of unknown size."
            )
            return self._result(
                TradeDecision.WATCH, reasons, sizing, exposures, holdings, policy, held
            )

        reward_to_risk = self._reward_to_risk(plan)
        if reward_to_risk is not None and reward_to_risk < _MIN_REWARD_TO_RISK:
            reasons.append(
                f"Setup pays {reward_to_risk:.2f}:1 — below the {_MIN_REWARD_TO_RISK:.0f}:1 "
                "floor. Entry sits too close to the first target relative to the stop, "
                "so the levels are not worth trading even though the view is bullish."
            )
            return self._result(
                TradeDecision.WATCH, reasons, sizing, exposures, holdings, policy, held
            )

        if not holdings.available:
            reasons.append(
                "Real holdings are unavailable, so concentration cannot be checked. "
                "Sizing below is portfolio-blind."
            )
            reasons.extend(holdings.warnings)
            return self._result(
                TradeDecision.WATCH, reasons, sizing, exposures, holdings, policy, held
            )

        equity = holdings.equity_value_myr
        if equity is None:
            reasons.append(
                "No holding could be priced, so exposure percentages have no "
                "denominator. Concentration unchecked."
            )
            reasons.extend(holdings.warnings)
            return self._result(
                TradeDecision.WATCH, reasons, sizing, exposures, holdings, policy, held
            )

        if held is not None and held.value_myr is None:
            # The candidate's own position could not be priced, so its current
            # exposure would read as 0% and the cap check would pass on a false
            # premise — the one case where a missing price flips the verdict.
            reasons.append(
                f"Already holding {held.shares:g} shares of {held.symbol} but that "
                "position is unpriced, so its current exposure cannot be measured. "
                "Concentration unverifiable for exactly this ticker."
            )
            reasons.extend(holdings.warnings)
            return self._result(
                TradeDecision.WATCH, reasons, sizing, exposures, holdings, policy, held
            )

        exposures = self._exposures(ticker_data, holdings, policy, sizing, held, equity)
        return self._decide(reasons, sizing, exposures, holdings, policy, held)

    @staticmethod
    def _reward_to_risk(plan: ActionPlan | None) -> float | None:
        """Reward:risk from the plan's own levels, or None when it cannot be formed."""
        if plan is None:
            return None
        entry, stop, target = plan.entry_limit, plan.stop_loss, plan.take_profit_1
        if entry is None or stop is None or target is None:
            return None
        risk = entry - stop
        if risk <= 0:
            return None
        return round((target - entry) / risk, 4)

    # ------------------------------------------------------------------
    # step 1-3: risk budget -> stop distance -> position size

    def _size(self, plan: ActionPlan | None, holdings: HoldingsSnapshot) -> PositionSizing:
        notes: list[str] = []
        entry = plan.entry_limit if plan else None
        stop = plan.stop_loss if plan else None

        if entry is None or stop is None:
            notes.append("No entry/stop pair on the action plan — cannot derive size.")
            return PositionSizing(
                risk_budget_pct=self.risk_budget_pct,
                risk_budget_source=_RISK_BUDGET_SOURCE,
                notes=notes,
            )

        if entry <= 0 or stop >= entry:
            notes.append(
                f"Stop (${stop:.2f}) is not below entry (${entry:.2f}) — "
                "stop distance is undefined for a long."
            )
            return PositionSizing(
                risk_budget_pct=self.risk_budget_pct,
                risk_budget_source=_RISK_BUDGET_SOURCE,
                notes=notes,
            )

        stop_distance_pct = round((entry - stop) / entry * 100, 4)
        raw_pct = self.risk_budget_pct / (stop_distance_pct / 100)

        capped_by: str | None = None
        position_pct = raw_pct
        if position_pct > _MAX_POSITION_PCT:
            position_pct = _MAX_POSITION_PCT
            capped_by = (
                f"single-position sanity rail ({_MAX_POSITION_PCT}% of equity sleeve); "
                f"risk-based size was {round(raw_pct, 2)}%"
            )
        elif position_pct < _MIN_POSITION_PCT:
            position_pct = _MIN_POSITION_PCT
            capped_by = (
                f"minimum tradable size ({_MIN_POSITION_PCT}%); "
                f"risk-based size was {round(raw_pct, 2)}%"
            )

        notes.append(
            f"A {stop_distance_pct:.2f}% stop distance risking "
            f"{self.risk_budget_pct}% of the sleeve implies a "
            f"{round(position_pct, 2)}% position."
        )
        if not holdings.fully_priced and holdings.available:
            notes.append(
                "Sleeve value excludes unpriced holdings, so this percentage is "
                "of a smaller-than-real denominator."
            )

        return PositionSizing(
            risk_budget_pct=self.risk_budget_pct,
            risk_budget_source=_RISK_BUDGET_SOURCE,
            stop_distance_pct=stop_distance_pct,
            suggested_position_pct=round(position_pct, 2),
            capped_by=capped_by,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # step 4: exposure caps

    def _exposures(
        self,
        ticker_data: TickerData,
        holdings: HoldingsSnapshot,
        policy: ConcentrationPolicy,
        sizing: PositionSizing,
        held,
        equity: float,
    ) -> list[ExposureCheck]:
        symbol = ticker_data.info.symbol.upper()
        add_pct = sizing.suggested_position_pct or 0.0
        checks: list[ExposureCheck] = []

        # --- single position ---
        current_value = held.value_myr if held and held.value_myr is not None else 0.0
        current_pct = round(current_value / equity * 100, 2)
        projected_pct = round(current_pct + add_pct, 2)
        cap = policy.max_single_position_pct_of_equity
        checks.append(
            self._check(
                label=f"single position: {symbol}",
                current_pct=current_pct,
                projected_pct=projected_pct,
                cap=cap,
                policy=policy,
                cap_key="concentration.max_single_position_pct_of_equity",
            )
        )

        # --- sector ---
        sector = ticker_data.info.sector
        if sector:
            sector_value = holdings.sector_value_myr(sector) or 0.0
            sector_current = round(sector_value / equity * 100, 2)
            sector_projected = round(sector_current + add_pct, 2)
            detail_suffix = (
                " Sector coverage is partial — some holdings have no sector on file."
                if holdings.missing_sector
                else ""
            )
            check = self._check(
                label=f"sector: {sector}",
                current_pct=sector_current,
                projected_pct=sector_projected,
                cap=policy.max_sector_pct_of_equity,
                policy=policy,
                cap_key="concentration.max_sector_pct_of_equity",
            )
            checks.append(check.model_copy(update={"detail": check.detail + detail_suffix}))

        # --- USD exposure ---
        usd_value = sum(
            h.value_myr for h in holdings.holdings if h.currency == "USD" and h.value_myr
        )
        usd_current = round(usd_value / equity * 100, 2)
        usd_projected = round(
            usd_current + (add_pct if ticker_data.info.currency.upper() == "USD" else 0.0), 2
        )
        checks.append(
            self._check(
                label="USD-denominated exposure",
                current_pct=usd_current,
                projected_pct=usd_projected,
                cap=policy.max_usd_pct_of_tracked_investable_assets,
                policy=policy,
                cap_key="concentration.max_usd_pct_of_tracked_investable_assets",
                cap_note=(
                    "Cap is defined against tracked investable assets (cash included); "
                    "measured here against the equity sleeve only, so it reads high."
                ),
            )
        )
        return checks

    def _check(
        self,
        *,
        label: str,
        current_pct: float,
        projected_pct: float,
        cap: float | None,
        policy: ConcentrationPolicy,
        cap_key: str,
        cap_note: str = "",
    ) -> ExposureCheck:
        if cap is None:
            reason = (
                f"{cap_key} is null in policy.yaml"
                if policy.available
                else "policy.yaml not found"
            )
            return ExposureCheck(
                label=label,
                current_pct=current_pct,
                projected_pct=projected_pct,
                cap_pct=None,
                status=ExposureStatus.CAP_UNCONFIGURED,
                detail=(
                    f"Now {current_pct:.2f}%, would become {projected_pct:.2f}%. "
                    f"No cap to compare against — {reason}. Not a pass."
                ),
            )

        breach = projected_pct > cap
        detail = (
            f"Now {current_pct:.2f}%, would become {projected_pct:.2f}% "
            f"against a {cap:.2f}% cap."
        )
        if cap_note:
            detail = f"{detail} {cap_note}"
        return ExposureCheck(
            label=label,
            current_pct=current_pct,
            projected_pct=projected_pct,
            cap_pct=cap,
            status=ExposureStatus.BREACH if breach else ExposureStatus.WITHIN_CAP,
            detail=detail,
        )

    # ------------------------------------------------------------------
    # step 5: decision

    def _decide(
        self,
        reasons: list[str],
        sizing: PositionSizing,
        exposures: list[ExposureCheck],
        holdings: HoldingsSnapshot,
        policy: ConcentrationPolicy,
        held,
    ) -> PortfolioGateResult:
        breaches = [c for c in exposures if c.status is ExposureStatus.BREACH]
        unconfigured = [c for c in exposures if c.status is ExposureStatus.CAP_UNCONFIGURED]

        already_over = [
            c
            for c in breaches
            if c.cap_pct is not None
            and c.current_pct is not None
            and c.current_pct > c.cap_pct
        ]

        if already_over:
            reasons.extend(
                f"Already over cap before adding — {c.label}: {c.detail}" for c in already_over
            )
            decision = TradeDecision.REJECT
        elif breaches:
            reasons.extend(
                f"Adding the full size would breach {c.label}: {c.detail}" for c in breaches
            )
            headroom = min(
                (c.cap_pct - c.current_pct)
                for c in breaches
                if c.cap_pct is not None and c.current_pct is not None
            )
            reasons.append(
                f"Trim to at most {round(max(headroom, 0.0), 2)}% of the equity "
                "sleeve to stay inside every cap."
            )
            decision = TradeDecision.REDUCE
        elif unconfigured:
            reasons.extend(f"{c.label}: {c.detail}" for c in unconfigured)
            reasons.append(
                "Concentration caps are unset, so no approval can be issued against "
                "them. Set concentration.* in policy.yaml to enable APPROVE."
            )
            decision = TradeDecision.WATCH
        else:
            reasons.append(
                "Risk-based size fits inside every configured concentration cap."
            )
            decision = TradeDecision.APPROVE

        if held is not None and decision is TradeDecision.APPROVE:
            reasons.append(
                f"Note: already holding {held.shares:g} shares — this is an add, "
                "not a new position."
            )
        reasons.extend(holdings.warnings)

        return self._result(
            decision, reasons, sizing, exposures, holdings, policy, held
        )

    def _result(
        self,
        decision: TradeDecision,
        reasons: list[str],
        sizing: PositionSizing,
        exposures: list[ExposureCheck],
        holdings: HoldingsSnapshot,
        policy: ConcentrationPolicy,
        held,
    ) -> PortfolioGateResult:
        return PortfolioGateResult(
            decision=decision,
            reasons=reasons,
            sizing=sizing,
            exposures=exposures,
            holdings_source=holdings.source,
            policy_source=policy.source,
            equity_sleeve_value=holdings.equity_value_myr,
            valuation_currency="MYR" if holdings.available else None,
            already_held=held is not None,
            held_shares=held.shares if held is not None else None,
        )
