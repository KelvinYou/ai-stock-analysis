from pydantic import BaseModel


class Settings(BaseModel):
    quick_think_model: str = "haiku"
    deep_think_model: str = "opus"
    synthesis_model: str = "sonnet"
    # Layer 3.5 adjudication. Sonnet rather than the debate's Opus: the ruling
    # reads arguments that already exist instead of generating new ones.
    research_manager_model: str = "sonnet"
    debate_rounds: int = 3
    data_dir: str = "data"
    price_history_period: str = "10y"

    # Layer 3.5 / 5 / 6 toggles. Each adds cost or a filesystem dependency, so
    # each can be turned off without touching the layers around it.
    enable_research_manager: bool = True
    enable_portfolio_gate: bool = True
    enable_outcome_memory: bool = True

    # Percent of the priced equity sleeve to risk per trade if the stop is hit.
    # See portfolio_gate.DEFAULT_RISK_BUDGET_PCT — a repo convention, not a
    # policy.yaml target.
    per_trade_risk_budget_pct: float = 0.5
