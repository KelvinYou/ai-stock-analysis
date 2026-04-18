from pydantic import BaseModel


class Settings(BaseModel):
    quick_think_model: str = "haiku"
    deep_think_model: str = "opus"
    synthesis_model: str = "sonnet"
    debate_rounds: int = 3
    data_dir: str = "data"
    price_history_period: str = "1y"
