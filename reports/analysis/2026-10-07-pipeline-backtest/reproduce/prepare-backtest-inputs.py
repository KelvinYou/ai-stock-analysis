import json,hashlib
from pathlib import Path
from datetime import date
from stock_analysis.backtest.replay import load_cash_rate_replay,load_macro_replay
from stock_analysis.models.market_data import TickerData
from stock_analysis.agents.technical import build_indicator_payload
R=Path('reports/analysis/2026-10-07-pipeline-backtest'); S=R/'session'
rows=load_cash_rate_replay(Path('/private/tmp/pipeline-backtest-dff.csv'),start_date=date(2025,9,1),end_date=date(2026,8,1))
p=R/'macro.jsonl';p.write_text('\n'.join(x.model_dump_json() for x in rows)+'\n')
manifest=json.loads((S/'manifest.json').read_text()); compact=[]; counts={k:0 for k in ['fundamentals','sentiment','macro','technical']}
for t in manifest['trials']:
 f=S/t['packet']; obj=json.loads(f.read_text()); asof=date.fromisoformat(t['as_of_date']); macro=load_macro_replay(p,asof)
 obj['ticker_data']['macro_snapshot']=macro.model_dump(mode='json') if macro else None
 obj['evidence_availability'].update(macro=bool(macro),macro_source='FRED:DFF; single-rate observation only')
 f.write_text(json.dumps(obj,indent=2)+'\n'); td=TickerData.model_validate(obj['ticker_data'])
 for k in counts:counts[k]+=bool(obj['evidence_availability'].get(k))
 compact.append(dict(ticker=t['ticker'],as_of_date=t['as_of_date'],evidence=obj['evidence_availability'],fundamentals=obj['ticker_data']['financials'],macro=obj['ticker_data']['macro_snapshot'],indicators=build_indicator_payload(td)))
(R/'inputs-compact.json').write_text(json.dumps(compact,indent=2)+'\n')
(R/'coverage.json').write_text(json.dumps(counts,indent=2)+'\n')
print(json.dumps(counts));print(json.dumps(compact[:1],indent=2))
