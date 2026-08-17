"""`.env` must reach the CLIs and stop there.

The repo ships a real `.env` selecting the Supabase backend. If library code
loaded it implicitly, this suite would start pointing at production storage on
any developer machine — so `load_env` is called from `cli()` only, and these
tests pin that boundary.
"""

from __future__ import annotations

import os

import stock_analysis.config as config_module
from stock_analysis.config import Settings, load_env


def test_from_env_does_not_read_a_dotenv_file(tmp_path, monkeypatch):
    """Settings.from_env is hermetic: only the real environment, never a file."""
    env_file = tmp_path / ".env"
    env_file.write_text("STORAGE_BACKEND=supabase\nSUPABASE_URL=https://leaked.example\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    settings = Settings.from_env()

    assert settings.storage_backend == "local"
    assert settings.supabase_url is None


def test_load_env_populates_the_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("STORAGE_BACKEND=supabase\nANALYSIS_WORKER_ID=from-dotenv\n")
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("ANALYSIS_WORKER_ID", raising=False)
    monkeypatch.setattr(config_module, "_ENV_LOADED", False)

    used = load_env(env_file)

    assert used == env_file
    settings = Settings.from_env()
    assert settings.storage_backend == "supabase"
    assert settings.worker_id == "from-dotenv"


def test_real_environment_wins_over_dotenv(tmp_path, monkeypatch):
    """A one-off `STORAGE_BACKEND=local stock-fetch ...` must beat the file."""
    env_file = tmp_path / ".env"
    env_file.write_text("STORAGE_BACKEND=supabase\n")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setattr(config_module, "_ENV_LOADED", False)

    load_env(env_file)

    assert Settings.from_env().storage_backend == "local"


def test_missing_dotenv_is_not_an_error(tmp_path, monkeypatch):
    """A machine with no .env must still run every CLI, on local defaults."""
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.setattr(config_module, "_ENV_LOADED", False)

    load_env(tmp_path / "nope.env")  # must not raise

    assert "STORAGE_BACKEND" not in os.environ
    assert Settings.from_env().storage_backend == "local"
