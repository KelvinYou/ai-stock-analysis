from pathlib import Path
import json,hashlib,subprocess,os
import pandas as pd
ROOT=Path('/Users/kelvin.you/Documents/dev/personal-os/repos/ai-stock-analysis')
OUT=Path(__file__).resolve().parent
PANELS={'primary8':['AVGO','NVDA','MSFT','TSM','V','UNH','ORCL','COST'],'prior11':['AAPL','AMZN','AVGO','GOOGL','META','MSFT','NVDA','TSLA','TSM','UNH','V'],'prior5':['AAPL','AMZN','GOOGL','MSFT','NVDA']}
runs=[{'panel':p,'slice':'full','start':'2018-01-01','end':'2026-08-14','cost':c} for p in PANELS for c in [10,20,50]]
runs += [{'panel':'primary8','slice':n,'start':a,'end':b,'cost':10} for n,a,b in [('early','2018-01-01','2023-12-31'),('middle','2024-01-01','2025-12-31'),('recent','2026-01-01','2026-08-14')]]
hashes={}
for n in sorted(set(sum(PANELS.values(),[]))):
 src=ROOT/'data'/n/'price_history.csv';hashes[n]=hashlib.sha256(src.read_bytes()).hexdigest()
 d=pd.read_csv(src);d=d[d.date<='2026-09-17'];dest=OUT/'prices'/n;dest.mkdir(parents=True);d.to_csv(dest/'price_history.csv',index=False)
protocol={'scope':'inspected-history research only; not fresh OOS','panels':PANELS,'runs':runs,'prices_capped':'2026-09-17','rule':{'lookback_months':12,'top_n':3},'source_hashes':hashes,'limitations':['surviving tracked universe','provider open/close dividend treatment unverified','cost assumptions not broker-calibrated','previous history inspected; all prior search not reconstructed'],'new_forecasts':0,'new_price_fetches':0}
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
env=dict(os.environ,STORAGE_BACKEND='local')
results=[]
for x in runs:
 name=f"{x['panel']}-{x['slice']}-{x['cost']}bps";target=OUT/name
 cmd=[str(ROOT/'.venv/bin/stock-analysis-backtest'),'--mode','cross-sectional','--tickers',','.join(PANELS[x['panel']]),'--start',x['start'],'--end',x['end'],'--cross-sectional-lookback-months','12','--cross-sectional-top-n','3','--cost-bps',str(x['cost']),'--data-dir',str(OUT/'prices'),'--experiment-ledger',str(OUT/'experiments.jsonl'),'--output',str(target)]
 p=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True);(OUT/f'{name}.log').write_text(p.stdout+p.stderr)
 if p.returncode: raise RuntimeError(p.stderr)
 r=json.loads(target.with_suffix('.json').read_text());keys=['periods','effective_n','oos_start','oos_end','net_compound_return','buy_and_hold_return','excess_return','max_drawdown','buy_and_hold_max_drawdown','strict_hold_log_excess_ci_95','matched_passive_log_excess_ci_95','net_p_value','price_basis','drawdown_basis']
 results.append(dict(x,**{k:r[k] for k in keys})); print(name,'PASS',flush=True)
assert all(hashlib.sha256((ROOT/'data'/n/'price_history.csv').read_bytes()).hexdigest()==h for n,h in hashes.items())
(OUT/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
print('ALL_COMPLETE',flush=True)
