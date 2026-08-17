"""Import the current flat ``data/`` snapshot into Supabase.

This is intentionally one-way and idempotent. It is a cutover tool, not a
runtime sync loop: after verification, use ``STORAGE_BACKEND=supabase`` so new
runs write directly to the cloud.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date
from pathlib import Path

from stock_analysis.config import Settings, load_env
from stock_analysis.data.cloud import SupabaseAnalysisStore, SupabaseError, SupabaseRestClient
from stock_analysis.data.store import DataStore
from stock_analysis.data.watchlist import load_watchlist_map
from stock_analysis.memory.cloud import SupabaseOutcomeStore
from stock_analysis.memory.outcomes import OutcomeStore

VALID_MARKETS = {"US", "MY"}


def preflight(client: SupabaseRestClient) -> None:
    """Fail loudly before writing anything if the cloud side is not ready.

    A dry run that only reads local files verifies the half of the migration
    that was never in doubt. This checks the half that is: URL, key, schema,
    whether the migration has actually been applied, and whether the key can
    write at all.
    """
    for table in ("tickers", "price_bars", "analysis_runs", "analysis_artifacts", "outcomes"):
        client.select(table, {"select": "*", "limit": "1"})
    client.select("latest_ticker_summary", {"select": "symbol", "limit": "1"})

    # Read access proves nothing about writes: `anon` can select every table
    # here, so a publishable key sails through the checks above and then fails
    # on the first real insert. Probe with a row that deliberately violates the
    # `market` check constraint — a key that may write gets a constraint error
    # (it reached the table), one that may not gets a permission/RLS error.
    # Either way nothing is persisted.
    try:
        client.upsert(
            "tickers",
            {"symbol": "__PREFLIGHT__", "market": "__INVALID__"},
            on_conflict="symbol",
        )
    except SupabaseError as exc:
        detail = str(exc).lower()
        if "row-level security" in detail or "permission denied" in detail:
            raise SupabaseError(
                "this key cannot write. Use SUPABASE_SERVICE_ROLE_KEY "
                "(Dashboard -> Project Settings -> API), not the publishable/anon key",
                exc.status_code,
            ) from exc
        return  # constraint rejection: the write path is open
    # An accepted row means the check constraint is missing, i.e. the applied
    # schema is not the one in supabase/migrations.
    client._request("DELETE", "tickers", params={"symbol": "eq.__PREFLIGHT__"})
    raise SupabaseError(
        "preflight row with market='__INVALID__' was accepted; the deployed schema "
        "is missing the tickers.market check constraint"
    )


def _check_local(data_dir: Path, local: DataStore, local_outcomes: OutcomeStore) -> list[str]:
    """Return constraint violations the database would reject on write."""
    problems: list[str] = []
    for directory in sorted(data_dir.iterdir()):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        symbol = directory.name.upper()
        ticker_data = local.load_market_data(symbol)
        if ticker_data and ticker_data.info.market.value not in VALID_MARKETS:
            problems.append(f"{symbol}: market {ticker_data.info.market.value!r} violates check")
        for record in local_outcomes.load(symbol):
            if not -1 <= record.conviction_score <= 1:
                problems.append(f"{symbol} @ {record.as_of_date}: conviction out of [-1, 1]")
            if not 0 <= record.signal_convergence <= 1:
                problems.append(f"{symbol} @ {record.as_of_date}: convergence out of [0, 1]")
            if record.horizon_days <= 0:
                problems.append(f"{symbol} @ {record.as_of_date}: horizon_days must be > 0")
    return problems


def import_data(data_dir: Path, settings: Settings, dry_run: bool = False) -> dict[str, int]:
    local = DataStore(data_dir)
    local_outcomes = OutcomeStore(data_dir)
    watch_map = load_watchlist_map(data_dir.parent / "tickers.txt")
    counts = {"tickers": 0, "market": 0, "briefings": 0, "outcomes": 0, "skipped": 0}

    # One HTTP client for the whole import. The per-run stores below share it so
    # a 30-ticker cutover does not open 30 connection pools.
    client = SupabaseRestClient(
        settings.supabase_url or "",
        settings.supabase_service_key or "",
        schema=settings.supabase_schema,
    )
    try:
        preflight(client)
        if dry_run:
            problems = _check_local(data_dir, local, local_outcomes)
            for problem in problems:
                print(f"WARN {problem}", file=sys.stderr)

        cloud = SupabaseAnalysisStore(settings, client=client)
        cloud_outcomes = SupabaseOutcomeStore(settings, client=client)

        for directory in sorted(data_dir.iterdir()):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            symbol = directory.name.upper()
            ticker_data = local.load_market_data(symbol)
            technicals = local.load_technicals(symbol)
            briefing = local.load_briefing(symbol)
            watch = watch_map.get(symbol)

            if ticker_data is None and briefing is None and not local_outcomes.load(symbol):
                # An empty per-ticker directory (a fetch that never produced
                # anything) is not a ticker. Counting it inflates the total the
                # operator is about to verify against.
                counts["skipped"] += 1
                continue

            if dry_run:
                counts["tickers"] += 1
                counts["market"] += int(ticker_data is not None)
                counts["briefings"] += int(briefing is not None)
                counts["outcomes"] += len(local_outcomes.load(symbol))
                continue

            if ticker_data:
                cloud.merge_market_data(symbol, ticker_data)
                counts["market"] += 1
            # Grouping and theme exist only as tickers.txt markers. Without this
            # the dashboard relabels every migrated ticker as an ungrouped
            # candidate, because that is its fallback for a NULL watch_group.
            cloud.upsert_ticker_metadata(
                symbol,
                market=(ticker_data.info.market.value if ticker_data else None)
                or (watch.market if watch else None),
                name=ticker_data.info.name if ticker_data else None,
                sector=ticker_data.info.sector if ticker_data else None,
                industry=ticker_data.info.industry if ticker_data else None,
                currency=ticker_data.info.currency if ticker_data else None,
                watch_group=watch.group if watch else None,
                theme=watch.theme if watch else None,
            )
            if technicals:
                cloud.save_technicals(symbol, technicals)

            # A current flat briefing becomes one immutable cloud run. The
            # deterministic UUID makes rerunning this importer update the same
            # artifact instead of creating duplicate history.
            if briefing:
                as_of = date.fromisoformat(briefing.date[:10])
                run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"import:{symbol}:{as_of}"))
                existing = cloud.get_run(run_id)
                if existing and existing.status == "completed":
                    # `begin_run` would upsert this row back to 'running', and
                    # both the RLS policy and the summary view hide non-completed
                    # runs — so a second import would blank live ticker pages.
                    counts["briefings"] += 1
                else:
                    run_store = SupabaseAnalysisStore(settings, run_id=run_id, client=client)
                    run_store.begin_run(
                        symbol,
                        as_of,
                        settings,
                        market=ticker_data.info.market.value if ticker_data else "US",
                    )
                    for _stage, loader, saver in (
                        (
                            "analyst_reports",
                            local.load_analyst_reports,
                            run_store.save_analyst_reports,
                        ),
                        ("debate_result", local.load_debate_result, run_store.save_debate_result),
                        (
                            "research_verdict",
                            local.load_research_verdict,
                            run_store.save_research_verdict,
                        ),
                    ):
                        model = loader(symbol)
                        if model:
                            saver(symbol, model, as_of)
                    run_store.save_briefing(symbol, briefing, as_of)
                    run_store.complete_run(run_id)
                    counts["briefings"] += 1

            records = local_outcomes.load(symbol)
            if records:
                counts["outcomes"] += cloud_outcomes.append(records)
            counts["tickers"] += 1
    finally:
        client.close()
    return counts


def cli() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Import flat stock-analysis data into Supabase.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env(storage_backend="supabase")
    try:
        counts = import_data(args.data_dir, settings, dry_run=args.dry_run)
    except SupabaseError as exc:
        print(f"ERR Supabase preflight failed: {exc}", file=sys.stderr)
        print(
            "Check SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY and that "
            "`supabase db push` has been run.",
            file=sys.stderr,
        )
        sys.exit(1)
    mode = "Would import" if args.dry_run else "Imported"
    print(
        f"{mode} {counts['tickers']} ticker(s), {counts['market']} market snapshot(s), "
        f"{counts['briefings']} briefing(s), {counts['outcomes']} outcome(s); "
        f"skipped {counts['skipped']} empty director(ies)."
    )


if __name__ == "__main__":
    cli()
