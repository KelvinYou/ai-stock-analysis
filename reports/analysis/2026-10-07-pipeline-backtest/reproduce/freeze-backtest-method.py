from pathlib import Path
import json,hashlib
R=Path('reports/analysis/2026-10-07-pipeline-backtest');S=R/'session'
m=json.loads((S/'manifest.json').read_text())
methods={
'actual_as_of_dates':m['as_of_dates'],
'interval_note':'Repository monthly schedules advance by30calendar days; this is12 windows, not first-day calendar-month dates.',
'arms':['official session consensus-only scoring10bps','same sealed trials20bps stress','production-parity score cap and four-report denominator10bps'],
'production_parity':'Use real compute_directional_consensus and compute_signal_convergence on all4typed reports; real calibrate_conviction_score(signal,rawmodelscore,consensus); real is_actionable. Directional signals failing gate become neutral. Portfolio sells skipped; scorer directional sells are hypothetical shorts and must not be called executed trades.',
'pipeline_scope':'Current-session compact replay: typed four analyst reports, two compact adversarial rounds and compact model synthesis. No authenticated provider, no full production ResearchManager/briefing/risk-plan replay. Daily OHLC scorer execution, no intraday stops or limits.',
'additional_limitations':['Batch analysts can see later-asof snapshots for the same ticker; cross-packet hindsight contamination cannot be excluded despite row-specific evidence instructions. This run is diagnostic, not blind/OOS evidence.','Current-provider historical financial statement values may include later revisions; filing clocks do not prove vintage values.','Exact model revision/training cutoff unavailable.'],
'sources':{'macro':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF','macro_availability':'observationdate+1day, official loader','SEC':'403 on company index and direct submissions; no complete replay','prices':'yfinance adjusted OHLC, no licensed PIT universe or delisting proof'},
'predictions_sealed':False}
(R/'method.json').write_text(json.dumps(methods,indent=2)+'\n')
prompts={}
for f in ['agents/fundamentals.py','agents/technical.py','agents/macro.py','agents/sentiment.py','debate/engine.py','synthesis/synthesizer.py','synthesis/risk_checker.py','backtest/session.py']:
 p=Path('src/stock_analysis')/f;prompts[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(R/'prompt-code-provenance.json').write_text(json.dumps(prompts,indent=2)+'\n')
print('Frozen methods and8source hashes; no outcomes read.')
