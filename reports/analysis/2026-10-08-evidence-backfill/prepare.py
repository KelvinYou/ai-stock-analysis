"""Prepare fresh enriched inputs against frozen pre-cutoff technical observations."""
from datetime import date, timedelta
from hashlib import sha256
import csv
import json
from pathlib import Path
from unittest.mock import patch

from stock_analysis.backtest.session import prepare_session_bundle, _load_sealed_packets, SessionManifest
from stock_analysis.models.market_data import TickerData

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / '2026-10-07-pipeline-backtest/session'


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, allow_nan=False) + '\n' for r in records))


def main():
    from validate_sources import validate
    validate()
    extracted = json.loads((HERE/'extracted.json').read_text())
    replay = HERE/'replay'
    for ticker, records in extracted.items():
        records.sort(key=lambda r:(r['fiscal_period_end'],r['available_as_of']))
        write_jsonl(replay/'fundamentals'/f'{ticker}.jsonl',records)
        basis = next(r['share_basis'] for r in reversed(records) if r['share_basis'])
        with (HERE/'raw'/f'{ticker}-valuation-prices.csv').open() as f:
            prices = list(csv.DictReader(f))
        assert not any(float(r['Stock Splits']) for r in prices if r['Date'][:10]>='2025-09-01')
        write_jsonl(replay/'valuation'/f'{ticker}.jsonl',[
            {'ticker':ticker,'price':float(r['Close']),'price_date':r['Date'][:10],
             'available_as_of':r['Date'][:10],'currency':'USD','share_basis':basis,
             'source':'Yahoo Finance Close; split-adjusted, dividend-unadjusted; retrieved 2026-10-08; end-of-day cutoff; provider-declared basis'}
            for r in prices if '2025-08-01'<=r['Date'][:10]<='2026-07-28'])
        # Issuer events are a restricted, selected news set, not an external sentiment archive.
        events={}
        for r in records:
            observation=next(iter(r['fact_provenance'].values()))
            events[observation['url']]={'ticker':ticker,
                'title':f"{ticker} published GAAP financial results for the quarter ended {r['fiscal_period_end']}",
                'publisher':ticker+' issuer','link':observation['url'],
                'published_at':observation['released'], 'available_as_of':r['available_as_of']}
        write_jsonl(replay/'news'/f'{ticker}.jsonl',list(events.values()))
    (replay/'manifest.json').write_text(json.dumps({'news':{'source':{'kind':'issuer_event_subset',
        'limitations':'Selected earnings announcements only; not full independent historical news coverage'}},
        'availability_policy':'Issuer release date plus one calendar day; price observation at end of session date'},indent=2)+'\n')
    manifest=SessionManifest.model_validate_json((OLD/'manifest.json').read_text())
    original={}
    macros={}
    frozen_hashes={}
    for item in manifest.trials:
        path=OLD/item['packet'];packet=json.loads(path.read_text())
        original[(item['ticker'],item['as_of_date'])]=packet
        frozen_hashes[str(path.relative_to(HERE.parent))]=sha256(path.read_bytes()).hexdigest()
        macro=packet['ticker_data'].get('macro_snapshot')
        if macro:macros[(macro['as_of_date'],macro['available_as_of'])]=macro
    write_jsonl(replay/'macro.jsonl',sorted(macros.values(),key=lambda r:r['available_as_of']))

    def frozen_fetch(fetcher,ticker):
        data=TickerData.model_validate(original[(ticker,fetcher.as_of_date.isoformat())]['ticker_data'])
        return data

    with patch('stock_analysis.backtest.session.BacktestFetcher.fetch',frozen_fetch):
        fresh=prepare_session_bundle(tickers=manifest.tickers,as_of_dates=manifest.as_of_dates,
            output_dir=HERE/'session-enriched',market=manifest.market,horizon_days=manifest.horizon_days,
            lookback_days=manifest.lookback_days,replay_dir=replay)
    packets=_load_sealed_packets(HERE/'session-enriched',fresh)
    counts={'statement':0,'growth':0,'valuation':0,'four_or_more_periods':0,'market_cap':0,'free_cash_flow':0,'issuer_events':0}
    by_ticker={t:{k:0 for k in counts} for t in manifest.tickers}
    for (ticker,as_of),packet in packets.items():
        old=original[(ticker,as_of.isoformat())]
        assert packet['ticker_data']['price_history']==old['ticker_data']['price_history']
        context=packet['fundamental_context'];ready=context['readiness'];financials=context['financials'] or {}
        observed={k:ready[k] for k in ('statement','growth','valuation')}
        observed.update(four_or_more_periods=ready['history_periods']>=4,
            market_cap=context['valuation']['market_cap'] is not None,
            free_cash_flow=financials.get('free_cash_flow') is not None,
            issuer_events=bool(packet['ticker_data']['news_headlines']))
        for key,value in observed.items():counts[key]+=int(value);by_ticker[ticker][key]+=int(value)
    for rel,h in frozen_hashes.items():assert sha256((HERE.parent/rel).read_bytes()).hexdigest()==h
    seal={str(p.relative_to(HERE)):sha256(p.read_bytes()).hexdigest() for p in sorted((HERE/'session-enriched').rglob('*.json'))}
    report={'status':'PASS','trials':len(packets),'coverage':counts,'by_ticker':by_ticker,
        'observations':{t:len(rs) for t,rs in extracted.items()},'frozen_technical_input_hashes':frozen_hashes,
        'new_session_hashes':seal,'new_predictions':0,'outcomes_scored':False,'future_source_rows_filtered_at_cutoff':True}
    (HERE/'coverage.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'frozen_technical_input_hashes','new_session_hashes'}},indent=2))


if __name__=='__main__':main()
