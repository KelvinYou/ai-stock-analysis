from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

_ENV_LOADED = False


def load_env(explicit_path: str | os.PathLike[str] | None = None) -> Path | None:
    """Load the repo's ``.env`` into the process environment. Returns the file used.

    Called from CLI entry points, deliberately not from ``Settings.from_env``:
    the library must stay hermetic, or a developer's local ``.env`` would leak
    into the test suite and quietly change which storage backend tests target.

    Real environment variables always win — ``load_dotenv`` does not override
    them — so `STORAGE_BACKEND=local pytest` and one-off overrides still work.
    """
    global _ENV_LOADED
    if _ENV_LOADED and explicit_path is None:
        return None
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:  # pragma: no cover - dotenv ships with pydantic-settings
        return None

    path = str(explicit_path) if explicit_path else find_dotenv(usecwd=True)
    if not path:
        _ENV_LOADED = True
        return None
    load_dotenv(path, override=False)
    _ENV_LOADED = True
    return Path(path)


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

    # Persistence is deliberately explicit. ``local`` keeps the historical
    # filesystem workflow available for tests and offline research; production
    # uses ``supabase`` and never writes analysis artifacts to ``data/``.
    storage_backend: Literal["local", "supabase"] = "local"
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    supabase_schema: str = "public"
    worker_poll_seconds: float = 5.0
    worker_id: str | None = None

    # Optional research enrichments. Each adds cost or a filesystem dependency,
    # so each can be turned off without touching the layers around it.
    enable_research_manager: bool = True
    enable_outcome_memory: bool = True

    @classmethod
    def from_env(cls, **overrides: Any) -> Settings:
        """Build settings from environment variables without persisting secrets.

        The publishable Supabase key is intentionally not accepted here. Python
        workers write through the service key; the browser uses its own
        publishable/anon key for read-only RLS-protected queries.
        """
        values: dict[str, Any] = {}
        env_map = {
            "storage_backend": "STORAGE_BACKEND",
            "data_dir": "STOCK_DATA_DIR",
            "supabase_url": "SUPABASE_URL",
            "supabase_service_key": "SUPABASE_SERVICE_ROLE_KEY",
            "supabase_schema": "SUPABASE_SCHEMA",
            "worker_id": "ANALYSIS_WORKER_ID",
            "worker_poll_seconds": "ANALYSIS_WORKER_POLL_SECONDS",
        }
        for field, env_name in env_map.items():
            raw = os.getenv(env_name)
            if raw is not None and raw != "":
                values[field] = raw

        if "worker_poll_seconds" in values:
            values["worker_poll_seconds"] = float(values["worker_poll_seconds"])

        values.update(overrides)
        return cls(**values)

    def pipeline_dump(self) -> dict[str, Any]:
        """Return safe settings for an ``analysis_runs`` row.

        Credentials and filesystem paths never enter the cloud job payload.
        """
        return self.model_dump(
            mode="json",
            exclude={
                "supabase_url",
                "supabase_service_key",
                "data_dir",
                "storage_backend",
                "supabase_schema",
                "worker_poll_seconds",
                "worker_id",
            },
        )
