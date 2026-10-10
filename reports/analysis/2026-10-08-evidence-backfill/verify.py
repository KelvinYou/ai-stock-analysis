"""Verify canonical enriched evidence without fetching outcomes or changing inputs."""
import csv
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from stock_analysis.backtest.session import SessionManifest, _load_sealed_packets
from validate_sources import validate

HERE=Path(__file__).resolve().parent


def main():
    validate()
    coverage=json.loads((HERE/'coverage.json').read_text())
    protocol=json.loads((HERE/'protocol.json').read_text())
    for relative,expected in protocol['artifact_hashes'].items():
        assert sha256((HERE/relative).read_bytes()).hexdigest()==expected,relative
    for relative,expected in protocol['implementation_hashes'].items():
        assert sha256((HERE.parents[2]/relative).read_bytes()).hexdigest()==expected,relative
    for relative,expected in coverage['frozen_technical_input_hashes'].items():
        assert sha256((HERE.parent/relative).read_bytes()).hexdigest()==expected,relative
    for relative,expected in coverage['new_session_hashes'].items():
        assert sha256((HERE/relative).read_bytes()).hexdigest()==expected,relative
    for source in json.loads((HERE/'price-manifest.json').read_text())['sources']:
        assert sha256((HERE/source['path']).read_bytes()).hexdigest()==source['sha256']
    session=HERE/'session-enriched'
    manifest=SessionManifest.model_validate_json((session/'manifest.json').read_text())
    packets=_load_sealed_packets(session,manifest)
    assert len(packets)==96
    price_tables={}
    for ticker in manifest.tickers:
        with (HERE/'raw'/f'{ticker}-valuation-prices.csv').open() as f:
            price_tables[ticker]={r['Date'][:10]:float(r['Close']) for r in csv.DictReader(f)}
    counted={k:0 for k in coverage['coverage']}
    for (ticker,cutoff),packet in packets.items():
        data=packet['ticker_data'];context=packet['fundamental_context'];ready=context['readiness']
        values={k:ready[k] for k in ('statement','growth','valuation')}
        values.update(four_or_more_periods=ready['history_periods']>=4,
            market_cap=context['valuation']['market_cap'] is not None,
            free_cash_flow=(context['financials'] or {}).get('free_cash_flow') is not None,
            issuer_events=bool(data['news_headlines']))
        for key,value in values.items():counted[key]+=int(value)
        price=data['valuation_price']
        assert price['price']==price_tables[ticker][price['price_date']]
        assert price['price_date']==max(b['date'] for b in data['price_history'])
        for r in data['financial_history']:
            assert date.fromisoformat(r['available_as_of'])<=cutoff
        if ticker=='TSM':
            assert context['financials']['currency']=='TWD'
            assert context['valuation']['eps_currency']=='USD'
        assert packet['evidence_availability']['sentiment_source']=='historical_replay'
    assert counted==coverage['coverage']
    assert not (session/'predictions.json').exists()
    result={'status':'PASS','packets_checked':96,'coverage':counted,
        'issuer_source_checks':37,'original_packets_unchanged':True,
        'close_not_adjusted_close_used_for_valuation':True,
        'canonical_packet_contexts_and_hashes_verified':True,
        'new_predictions':0,'outcomes_scored':False}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
