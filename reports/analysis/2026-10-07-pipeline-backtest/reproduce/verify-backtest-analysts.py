import json
from pathlib import Path
from stock_analysis.models.agent_reports import AnalystReports
R=Path('reports/analysis/2026-10-07-pipeline-backtest'); roles={r:{(x['ticker'],x['as_of_date']):x['report'] for x in json.loads((R/f'{r}-reports.json').read_text())} for r in ['fundamentals','technical','macro','sentiment']}
inputs=json.loads((R/'inputs-compact.json').read_text())
for x in inputs:
 k=x['ticker'],x['as_of_date'];a=AnalystReports.model_validate({r:rows[k] for r,rows in roles.items()});assert a.technical.rsi_14==x['indicators']['rsi_14']
 for r in ['fundamentals','sentiment','macro']:
  if not x['evidence'][r]:assert getattr(a,r).signal.value=='neutral' and getattr(a,r).confidence.value=='low'
assert all(len(v)==96 for v in roles.values());print('96 complete four-report sets; factual RSI and missing-evidence neutral guards verified.')
