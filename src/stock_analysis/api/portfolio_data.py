"""Run-scoped portfolio input adapter; latest flat files are never mixed."""

from stock_analysis.config import Settings
from stock_analysis.data.cloud import SupabaseAnalysisStore
from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.synthesis import Briefing
from stock_analysis.portfolio import PortfolioBundle, PortfolioSnapshot
from stock_analysis.synthesis.signal_views import SessionPrediction


def snapshot_from_run(run_id, data, reports, briefing, *, input_hash=None, provenance=None):
    if briefing.ticker != data.info.symbol or briefing.data_as_of != str(max(b.date for b in data.price_history)):
        raise ValueError("Completed briefing is not bound to the portfolio price snapshot")
    return PortfolioSnapshot(
        run_id=run_id, ticker_data=data, source_input_hash=input_hash,
        provider_provenance=provenance or {},
        source_synthesized_signal=briefing.synthesized_signal,
        source_signal_gate_reasons=briefing.signal_gate_reasons,
        prediction=SessionPrediction(
            ticker=briefing.ticker, as_of_date=briefing.date,
            overall_signal=briefing.overall_signal, conviction_score=briefing.conviction.score,
            signal_convergence=briefing.conviction.signal_convergence,
            agent_signals={role: getattr(reports, role).signal
                           for role in ("fundamentals", "technical", "sentiment", "macro")},
            agent_confidences={role: getattr(reports, role).confidence
                               for role in ("fundamentals", "technical", "sentiment", "macro")},
        ),
    )


def load_portfolio_bundle(settings: Settings, run_ids: list[str], local_snapshots=None):
    rows = []
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("Duplicate portfolio run IDs")
    for run_id in run_ids:
        if settings.storage_backend == "local":
            snapshot = (local_snapshots or {}).get(run_id)
            if snapshot is None:
                raise ValueError("Completed run-bound portfolio input not found")
        else:
            store = SupabaseAnalysisStore(settings, run_id=run_id)
            try:
                run = store.get_run(run_id)
                if run is None or run.status != "completed":
                    raise ValueError("Portfolio requires completed analysis runs")
                data = store.load_run_input()
                reports = store.resume_artifact("analyst_reports", AnalystReports)
                briefing = store.resume_artifact("briefing", Briefing)
                if data is None or reports is None or briefing is None:
                    raise ValueError("Portfolio requires sealed input and complete run-bound stages")
                if run.symbol != data.info.symbol or run.as_of_date != store._run_as_of:
                    raise ValueError("Portfolio run/input identity mismatch")
                if briefing.date != str(run.as_of_date):
                    raise ValueError("Portfolio briefing/run decision date mismatch")
                snapshot = snapshot_from_run(
                    run_id, data, reports, briefing, input_hash=store._input_hash,
                    provenance={"run_settings": run.settings, "authenticated_provider_verified": False},
                )
            finally:
                store.close()
        rows.append(snapshot)
    dates = {row.prediction.as_of_date for row in rows}
    if len(dates) != 1:
        raise ValueError("Portfolio runs must share one decision date")
    return PortfolioBundle(as_of_date=next(iter(dates)), snapshots=rows)
