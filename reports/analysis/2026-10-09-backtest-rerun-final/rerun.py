"""Offline fixed-forecast revalidation; no new predictions or provider outcomes."""
import json
import runpy
from collections import Counter
from hashlib import sha256
from pathlib import Path

from stock_analysis.backtest.experiment_ledger import append_experiment_record, build_experiment_record
from stock_analysis.backtest.portfolio import PortfolioConfig, simulate, to_markdown
from stock_analysis.backtest.runner import BacktestResult
from stock_analysis.backtest.session import (
    SessionManifest, _load_sealed_packets, calibrate_session_prediction,
    load_session_predictions, recalibrate_session_result,
)
from stock_analysis.models.market_data import TickerData
from stock_analysis.synthesis.risk_checker import RiskChecker

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = HERE.parent / '2026-10-07-pipeline-backtest'
FT = HERE.parent / '2026-10-08-ft-backtest'
SESSION = OLD / 'session'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def dump(name, value):
    path = HERE / name
    if path.exists():
        raise FileExistsError(f'Refusing to overwrite rerun artifact: {path}')
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    source = FT / 'pipeline-10bps.json'
    seal = json.loads((OLD / 'seal.json').read_text())
    for name, checksum in seal['files'].items():
        assert digest(OLD / name) == checksum
    namespace = runpy.run_path(str(FT / 'compare.py'))
    source_files = [source, OLD / 'seal.json', SESSION / 'manifest.json',
                    SESSION / 'predictions.json', FT / 'compare.py']
    code_files = list((ROOT / 'src/stock_analysis').rglob('*.py'))
    protocol = {
        'scope': 'Post-hoc fixed forecast and outcome rerun; no new LLM forecasts; no promotion evidence',
        'panel': 'Original 96 trials, eight surviving tickers, unchanged dates and 30-day horizon',
        'input_hashes': {str(p.relative_to(ROOT)): digest(p) for p in source_files},
        'implementation_hashes': {str(p.relative_to(ROOT)): digest(p) for p in code_files},
        'script_sha256': digest(Path(__file__)), 'costs_bps_per_side': [0, 10, 20],
        'strategies': namespace['DEFAULTS'] + namespace['ARMS'],
        'rule': 'Reuse fixed FT rules with current evidence/confidence guards and shared risk eligibility',
        'limitation': 'Old incomplete evidence only; enriched 96-packet panel has no new forecasts; historical outcomes already seen',
    }
    dump('protocol.json', protocol)
    original = BacktestResult.model_validate(json.loads(source.read_text())['result'])
    result = recalibrate_session_result(original, SESSION)
    manifest = SessionManifest.model_validate_json((SESSION / 'manifest.json').read_text())
    packets = _load_sealed_packets(SESSION, manifest)
    predictions = load_session_predictions(SESSION)
    traces = []
    for trial in result.trials:
        key = (trial.ticker, trial.as_of_date)
        packet = packets[key]
        data = TickerData.model_validate(packet['ticker_data'])
        evidence = packet['evidence_availability']
        calibrated = calibrate_session_prediction(predictions[key], ticker_data=data,
            fundamentals_available=bool(evidence.get('fundamentals')),
            sentiment_available=bool(evidence.get('sentiment')), macro_available=bool(evidence.get('macro')))
        signals, score, convergence = namespace['derive'](trial, calibrated.model_dump(mode='json'))
        note = RiskChecker().plan_levels(data, score, convergence).note
        if note:
            signals = {name: 'neutral' for name in signals}
        trial.agent_signals.update(signals)
        traces.append({'ticker': trial.ticker, 'as_of_date': str(trial.as_of_date),
                       'ft_signals': signals, 'ft_score': score, 'ft_convergence': convergence,
                       'risk_decline_note': note, 'pipeline_signal': trial.overall_signal.value,
                       'pipeline_gate_reasons': trial.signal_gate_reasons})
    assert len(result.trials) == len(traces) == 96
    dump('result.json', result.model_dump(mode='json'))
    dump('signal-trace.json', traces)
    summary = {}
    for cost in protocol['costs_bps_per_side']:
        config = PortfolioConfig(cost_bps_per_side=cost)
        report = simulate(result, config, strategies=protocol['strategies'])
        assert report.n_strategies_tested == 11
        assert all(t.entry_date > t.as_of_date for t in result.trials)
        reversed_result = result.model_copy(deep=True)
        reversed_result.trials.reverse()
        reverse = simulate(reversed_result, config, strategies=protocol['strategies'])
        assert [(r.strategy, r.total_return_pct) for r in report.strategies] == [(r.strategy, r.total_return_pct) for r in reverse.strategies]
        record = build_experiment_record(mode='fixed-forecast-revalidation',
            result=result.model_dump(mode='json'), portfolio=report.model_dump(mode='json'),
            cross_sectional_trial_allocation=None, signal_ablation=None,
            config={'protocol': protocol, 'cost_bps_per_side': cost}, diagnostics={'new_forecasts': 0})
        record = append_experiment_record(HERE / 'experiments.jsonl', record)
        dump(f'comparison-{cost}bps.json', {'portfolio': report.model_dump(mode='json'), 'experiment': record})
        (HERE / f'comparison-{cost}bps.md').write_text(to_markdown(report))
        fields = ('strategy', 'total_return_pct', 'excess_return_pct', 'n_trades',
                  'max_drawdown_pct', 'effective_n', 'deflated_sharpe', 'strict_hold_log_excess_ci_95')
        summary[cost] = [{k: getattr(r, k) for k in fields} for r in report.strategies
                        if r.strategy in ['overall', 'ft_weighted', 'ft_agreement', 'buy_and_hold', 'technical']]
    for name, checksum in seal['files'].items():
        assert digest(OLD / name) == checksum
    for name, checksum in protocol['input_hashes'].items():
        assert digest(ROOT / name) == checksum
    dump('summary.json', {'costs': summary, 'pipeline_signals': dict(Counter(t.overall_signal.value for t in result.trials)),
        'original_sealed_files_unchanged': len(seal['files']), 'trial_order_invariance': True,
        'new_forecasts': 0, 'new_price_fetches': 0})
    print(json.dumps(summary[10], indent=2))


if __name__ == '__main__':
    main()
