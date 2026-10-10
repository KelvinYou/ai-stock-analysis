from pathlib import Path
from datetime import date,datetime,timezone
import hashlib,json,math
import pandas as pd
from stock_analysis.backtest.cross_sectional import CrossSectionalConfig,run_cross_sectional_backtest,to_markdown
from stock_analysis.backtest.main import _append_standalone_experiment
from types import SimpleNamespace
ROOT=Path('/Users/kelvin.you/Documents/dev/personal-os/repos/ai-stock-analysis');OUT=ROOT/'reports/analysis/2026-10-09-momentum-validation-extended';BASE=ROOT/'reports/analysis/2026-10-09-momentum-reliability'
names=['AVGO','COST','MSFT','NVDA','ORCL','TSM','UNH','V'];source=BASE/'return-source-audit-network'
runs=[{'snapshot':v,'cost_bps':c,'bootstrap_block_months':3} for v in ['original','current_adjusted'] for c in [20,40,80]]
runs += [{'snapshot':'current_adjusted','cost_bps':20,'bootstrap_block_months':b} for b in [6,12]]
files=[source/f'{n}-unadjusted-actions.csv' for n in names]+[Path('/private/tmp/momentum-reliability-20261009/prices')/n/'price_history.csv' for n in names]
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
protocol={'prepared_at_utc':datetime.now(timezone.utc).isoformat(),'status':'post_hoc_research_only','panels':names,'lookback_months':12,'top_n':3,'signal_dates':['2018-01-01','2026-08-14'],'runs':runs,'cost_status':'user_authorized_research_budget_not_calibrated','base_cost_bps_per_side':20,'stress_costs_bps_per_side':[40,80],'cost_scope':'proportional transaction-cost budget; no independently calibrated broker minimum, FX, dividend tax or fills','rolling_diagnostic_months':24,'roll_step_months':1,'input_hashes':hashes,'parameter_selection':'all scenarios reported; no winner selection; previous searches unresolved','historical_oos_claim':False}
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
original={};current={};actions={}
for n in names:
 original[n]=pd.read_csv(Path('/private/tmp/momentum-reliability-20261009/prices')/n/'price_history.csv')
 f=pd.read_csv(source/f'{n}-unadjusted-actions.csv');f['date']=f.iloc[:,0].str[:10];ratio=f['Adj Close']/f['Close'];current[n]=pd.DataFrame({'date':f.date,'open':f.Open*ratio,'close':f['Adj Close']})
 events=f[f.Dividends!=0].copy();rt=(f['Close']+f['Dividends'])/f['Close'].shift(1);adj=f['Adj Close']/f['Adj Close'].shift(1);events['cash_dividend_reinvest_at_close_return']=rt.loc[events.index]-1;events['provider_adjusted_close_return']=adj.loc[events.index]-1;events['difference']=rt.loc[events.index]-adj.loc[events.index];events[['date','Dividends','cash_dividend_reinvest_at_close_return','provider_adjusted_close_return','difference']].to_csv(OUT/f'{n}-dividend-convention.csv',index=False)
 actions[n]={'events':len(events),'maximum_absolute_daily_return_convention_difference':float(events['difference'].abs().max()),'explanation':'Declared synthetic reinvest-at-close arithmetic differs from provider adjusted-return convention; not a broker cash ledger or proof of provider error. Yahoo unadjusted OHLC is already split-adjusted, so no second split adjustment.'}
summary=[];reports={}
for r in runs:
 key=f"{r['snapshot']}-{r['cost_bps']}bps-block{r['bootstrap_block_months']}";hist=original if r['snapshot']=='original' else current
 rep=run_cross_sectional_backtest(hist,start=date(2018,1,1),end=date(2026,8,14),config=CrossSectionalConfig(lookback_months=12,top_n=3,cost_bps_per_side=r['cost_bps'],bootstrap_block_periods=r['bootstrap_block_months']))
 payload=rep.model_dump(mode='json');(OUT/f'{key}.json').write_text(json.dumps(payload,indent=2)+'\n');(OUT/f'{key}.md').write_text(to_markdown(rep));reports[key]=payload
 _append_standalone_experiment('cross-sectional',payload,hist,SimpleNamespace(experiment_ledger=OUT/'experiments.jsonl'))
 summary.append(dict(r,**{k:payload[k] for k in ['periods','effective_n','net_compound_return','buy_and_hold_return','excess_return','max_drawdown','buy_and_hold_max_drawdown','strict_hold_log_excess_ci_95','matched_passive_log_excess_ci_95']}));print(key,'DONE',flush=True)
old=reports['original-20bps-block3'];new=reports['current_adjusted-20bps-block3'];assert len(old['period_log'])==len(new['period_log'])==103
changed=[{'date':a['as_of_date'],'old':a['selected_tickers'],'new':b['selected_tickers']} for a,b in zip(old['period_log'],new['period_log'],strict=True) if set(a['selected_tickers'])!=set(b['selected_tickers'])]
roll=[]
rows=new['period_log']
for end in range(24,len(rows)+1):
 x=rows[end-24:end];logex=sum(math.log1p(p['net_return'])-math.log1p(p['strict_hold_net_return']) for p in x);roll.append({'first_signal':x[0]['as_of_date'],'last_signal':x[-1]['as_of_date'],'periods':24,'log_excess':logex,'relative_wealth_advantage':math.expm1(logex)})
# Rolling windows preserve actual stored ongoing strategy/hold cost legs; do not reset portfolios or charge new initial/final fees.
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
results={'scenarios':summary,'changed_selection_months':changed,'rolling_24m':{'windows':len(roll),'winning_windows':sum(x['log_excess']>0 for x in roll),'minimum_relative_advantage':min(x['relative_wealth_advantage'] for x in roll),'maximum_relative_advantage':max(x['relative_wealth_advantage'] for x in roll),'rows':roll},'dividend_convention':actions,'original_inputs_unchanged':True,'promotion_ready':False}
(OUT/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
print('COMPLETE',len(changed),results['rolling_24m']['winning_windows'],len(roll),flush=True)
