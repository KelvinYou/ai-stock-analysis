from __future__ import annotations

from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260818000002_queue_admission_contract.sql"
)
FRESH_MIGRATION = Path("supabase/migrations/20260818000000_deployment_safety.sql")


def test_queue_admission_migration_uses_request_identity_and_durable_queue():
    for migration in (MIGRATION, FRESH_MIGRATION):
        sql = migration.read_text()

        assert "p_quota_timezone text default 'Asia/Kuala_Lumpur'" in sql
        assert (
            "v_request_date date := coalesce(p_as_of_date, (now() at time zone v_quota_timezone)::date);"
            in sql
        )
        assert "p_max_concurrent_runs" not in sql
        assert "analysis_idempotency_conflict" in sql
        assert "v_existing.settings is distinct from v_request_settings" in sql
        assert "status = 'running'" not in sql.split("create or replace function public.enqueue_analysis_run", 1)[1].split("$$;", 1)[0]
