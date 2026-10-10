import json
from pathlib import Path
from argparse import Namespace
from stock_analysis.backtest.runner import BacktestResult
from stock_analysis.models.agent_reports import Signal
from stock_analysis.backtest.main import _score_and_write
R=Path('reports/analysis/2026-10-07-pipeline-backtest'); payload=json.loads((R/'session-10bps.json').read_text()); result=BacktestResult.model_validate(payload['result'])
parity={(x['ticker'],x['as_of_date']):x for x in json.loads((R/'production-parity-predictions.json').read_text())}
trials=[]
for t in result.trials:
 p=parity[t.ticker,t.as_of_date.isoformat()];reasons=['production_parity_research_arm']
 if p['overall_signal']!=p['raw_signal']:reasons.append('production_actionability_gate_failed')
 trials.append(t.model_copy(update={'overall_signal':Signal(p['overall_signal']),'conviction_score':p['conviction_score'],'signal_convergence':p['signal_convergence'],'signal_gate_reasons':reasons}))
settings=dict(result.settings);settings['parity_arm']='real production four-report consensus and min(model score,consensus); not full limit-stop execution'
result=result.model_copy(update={'trials':trials,'settings':settings})
a=Namespace(mode='rescore',cost_bps=10.0,starting_balance=10000.0,position_size=.10,allow_short=False,cash_rate_replay=None,output=str(R/'production-parity-10bps'),experiment_ledger=R/'experiments.jsonl',_rescore_allocator_histories=payload['allocator_price_histories'],market='US',start=None,end=None,interval=None,cross_sectional_lookback_months=12,cross_sectional_top_n=3,data_dir='data')
_score_and_write(result,a)
