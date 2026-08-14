from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.synthesis import Briefing, ConvictionScore, RiskAssessment


def test_default_settings_have_no_personal_portfolio_gate():
    settings = Settings()

    assert not hasattr(settings, "enable_portfolio_gate")
    assert not hasattr(settings, "per_trade_risk_budget_pct")


def test_briefing_is_research_only():
    briefing = Briefing(
        ticker="TEST",
        date="2026-08-14",
        overall_signal=Signal.NEUTRAL,
        conviction=ConvictionScore(
            score=0.0,
            signal_convergence=0.5,
            explanation="mixed evidence",
        ),
        executive_summary="Research summary",
        bull_case="Bull case",
        bear_case="Bear case",
        key_uncertainties=[],
        catalysts_upcoming=[],
        risk_assessment=RiskAssessment(
            correlation_notes=[],
            max_drawdown_scenario="unknown",
        ),
        agent_signal_breakdown={},
    )

    assert {
        "portfolio_gate",
        "trade_decision",
        "position_size_suggestion",
        "research_view",
    }.isdisjoint(briefing.model_dump())
