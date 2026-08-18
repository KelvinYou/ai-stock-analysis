from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator

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
    environment: Literal["development", "production"] = "development"
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

    # Control-plane protection and admission limits. These are intentionally
    # not part of the persisted pipeline settings: they govern the service,
    # not the analysis result.
    api_bearer_token: str | None = None
    max_daily_runs: int = Field(default=10, ge=1)
    # Supabase evaluates the daily cost gate in this timezone. Keep it explicit
    # so a container's host timezone cannot silently change the quota boundary.
    quota_timezone: str = "Asia/Kuala_Lumpur"
    max_concurrent_runs: int = Field(default=1, ge=1)
    max_run_seconds: int = Field(default=1800, ge=60)
    worker_lease_seconds: int = Field(default=900, ge=60)
    worker_heartbeat_seconds: int = Field(default=60, ge=5)

    # Optional research enrichments. Each adds cost or a filesystem dependency,
    # so each can be turned off without touching the layers around it.
    enable_research_manager: bool = True
    enable_outcome_memory: bool = True

    @model_validator(mode="after")
    def validate_worker_timing(self) -> Settings:
        if self.worker_heartbeat_seconds >= self.worker_lease_seconds:
            raise ValueError("worker_heartbeat_seconds must be shorter than worker_lease_seconds")
        try:
            ZoneInfo(self.quota_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"quota_timezone is not a valid IANA timezone: {self.quota_timezone}") from exc
        return self

    @classmethod
    def from_env(cls, **overrides: Any) -> Settings:
        """Build settings from environment variables without persisting secrets.

        The publishable Supabase key is intentionally not accepted here. Python
        workers write through the service key; the browser uses its own
        publishable/anon key for read-only RLS-protected queries.
        """
        values: dict[str, Any] = {}
        env_map = {
            "environment": "APP_ENV",
            "storage_backend": "STORAGE_BACKEND",
            "data_dir": "STOCK_DATA_DIR",
            "supabase_url": "SUPABASE_URL",
            "supabase_service_key": "SUPABASE_SERVICE_ROLE_KEY",
            "supabase_schema": "SUPABASE_SCHEMA",
            "worker_id": "ANALYSIS_WORKER_ID",
            "worker_poll_seconds": "ANALYSIS_WORKER_POLL_SECONDS",
            "api_bearer_token": "API_BEARER_TOKEN",
            "max_daily_runs": "ANALYSIS_MAX_DAILY_RUNS",
            "quota_timezone": "ANALYSIS_QUOTA_TIMEZONE",
            "max_concurrent_runs": "ANALYSIS_MAX_CONCURRENT_RUNS",
            "max_run_seconds": "ANALYSIS_MAX_RUN_SECONDS",
            "worker_lease_seconds": "ANALYSIS_WORKER_LEASE_SECONDS",
            "worker_heartbeat_seconds": "ANALYSIS_WORKER_HEARTBEAT_SECONDS",
        }
        for field, env_name in env_map.items():
            raw = os.getenv(env_name)
            if raw is not None and raw != "":
                values[field] = raw

        if "worker_poll_seconds" in values:
            values["worker_poll_seconds"] = float(values["worker_poll_seconds"])

        for field in {
            "max_daily_runs",
            "max_concurrent_runs",
            "max_run_seconds",
            "worker_lease_seconds",
            "worker_heartbeat_seconds",
        }:
            if field in values:
                values[field] = int(values[field])

        values.update(overrides)
        return cls(**values)

    def require_api_runtime(self) -> None:
        """Fail closed when the control plane is configured for production."""
        if self.environment != "production":
            return
        missing: list[str] = []
        if self.storage_backend != "supabase":
            missing.append("STORAGE_BACKEND=supabase")
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not self.api_bearer_token:
            missing.append("API_BEARER_TOKEN")
        if missing:
            raise RuntimeError(
                "Production API configuration is incomplete: " + ", ".join(missing)
            )

    def require_worker_runtime(self) -> None:
        """Fail closed when a production worker has no outbound LLM auth."""
        if self.environment != "production":
            return
        missing: list[str] = []
        if self.storage_backend != "supabase":
            missing.append("STORAGE_BACKEND=supabase")
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not os.getenv("ANTHROPIC_API_KEY"):
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            raise RuntimeError(
                "Production worker configuration is incomplete: " + ", ".join(missing)
            )

    def pipeline_dump(self) -> dict[str, Any]:
        """Return safe settings for an ``analysis_runs`` row.

        Credentials and filesystem paths never enter the cloud job payload.
        """
        return self.model_dump(
            mode="json",
            exclude={
                "environment",
                "supabase_url",
                "supabase_service_key",
                "data_dir",
                "storage_backend",
                "supabase_schema",
                "worker_poll_seconds",
                "worker_id",
                "api_bearer_token",
                "max_daily_runs",
                "quota_timezone",
                "max_concurrent_runs",
                "max_run_seconds",
                "worker_lease_seconds",
                "worker_heartbeat_seconds",
            },
        )
