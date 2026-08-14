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

    # Optional research enrichments. Each adds cost or a filesystem dependency,
    # so each can be turned off without touching the layers around it.
    enable_research_manager: bool = True
    enable_outcome_memory: bool = True
