from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
import yfinance as yf
ROOT=Path('/Users/kelvin.you/Documents/dev/personal-os/repos/ai-stock-analysis')
OUT=ROOT/'reports/analysis/2026-10-09-momentum-reliability/return-source-audit-network';OUT.mkdir(exist_ok=False)
summary={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'current-provider supplementary vintage; not replacement for original sealed prices','requested_range':['2016-04-22','2026-09-18'],'source':'Yahoo Finance via yfinance','auto_adjust':False,'actions':True,'tickers':{}}
for n in ['AVGO','COST','MSFT','NVDA','ORCL','TSM','UNH','V']:
 try:
  d=yf.Ticker(n).history(start='2016-04-22',end='2026-09-18',auto_adjust=False,actions=True,timeout=15,raise_errors=True)
  if d.empty:raise ValueError('empty response')
  p=OUT/f'{n}-unadjusted-actions.csv';d.to_csv(p)
  fields=['Dividends','Stock Splits'];actions=d.loc[(d[fields]!=0).any(axis=1),fields];actions.to_csv(OUT/f'{n}-actions.csv')
  summary['tickers'][n]={'status':'CAPTURED_CURRENT_PROVIDER_UNVERIFIED','rows':len(d),'columns':list(d.columns),'dividend_events':int((d['Dividends']!=0).sum()),'split_events':int((d['Stock Splits']!=0).sum()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'adj_close_available':'Adj Close' in d.columns}
 except Exception as e:
  summary['tickers'][n]={'status':'UNAVAILABLE','error_type':type(e).__name__,'error':str(e)[:300]}
 print(n,summary['tickers'][n]['status'],flush=True)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
