"""Capture unadjusted-dividend price observations, with split adjustment disclosed."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
import json
from hashlib import sha256
import yfinance as yf

HERE=Path(__file__).resolve().parent
TICKERS=['AVGO','NVDA','MSFT','TSM','V','UNH','ORCL','COST']

def fetch(ticker):
    path=HERE/'raw'/f'{ticker}-valuation-prices.csv'
    if not path.exists():
        data=yf.Ticker(ticker).history(start='2024-06-01',end='2026-10-09',auto_adjust=False,back_adjust=False,actions=True)
        if data.empty:raise RuntimeError('No prices for '+ticker)
        data.to_csv(path)
    return {'ticker':ticker,'path':str(path.relative_to(HERE)),'sha256':sha256(path.read_bytes()).hexdigest(),
            'provider':'Yahoo Finance via yfinance; Close is split adjusted, not dividend adjusted; current retrieved vintage',
            'corporate_action_completeness':'provider_declared_not_independently_authenticated'}
if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(fetch,TICKERS))
    (HERE/'price-manifest.json').write_text(json.dumps({'retrieved_at':datetime.now(UTC).isoformat(),'sources':rows},indent=2)+'\n')
    print('Price files:',len(rows))
