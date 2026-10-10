"""Source integrity and regression checks before any financial observation is trusted."""
from datetime import date, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path

from stock_analysis.models.market_data import FinancialStatements

HERE=Path(__file__).resolve().parent


def validate():
    assert json.loads((HERE/'extraction-errors.json').read_text())==[]
    downloaded=json.loads((HERE/'download-manifest.json').read_text())['sources']
    sources={r['path']:r for r in downloaded if r['status']!='failed'}
    for path,source in sources.items():
        assert sha256((HERE/path).read_bytes()).hexdigest()==source['sha256']
    series=json.loads((HERE/'extracted.json').read_text())
    records={(t,r['fiscal_period_end']):r for t,rs in series.items() for r in rs}
    checked=0
    for rs in series.values():
        for record in rs:
            FinancialStatements.model_validate(record)
            start,end,available=[date.fromisoformat(record[k]) for k in ('fiscal_period_start','fiscal_period_end','available_as_of')]
            assert start<=end<available
            for name in ('revenue','net_income','diluted_eps'):
                assert record[name] is not None and math.isfinite(record[name])
                assert record['fact_provenance'][name]['selector_or_excerpt']
            for provenance in record['fact_provenance'].values():
                source=sources[provenance['source_file']]
                assert provenance['source_sha256']==source['sha256']
                assert provenance['url']==source['url']
                assert date.fromisoformat(provenance['released'])+timedelta(days=1)==available
            checked+=1
    # Independently checked issuer table/cover observations. These catch the
    # weighted-share/EPS, outlook/quarter, PDF layout and fiscal-YTD mistakes.
    golden={
        ('V','2025-06-30'):{'net_income':5.272e9,'diluted_eps':2.69,'free_cash_flow':6.309e9},
        ('V','2025-03-31'):{'net_income':4.577e9,'diluted_eps':2.32},
        ('AVGO','2025-05-04'):{'diluted_eps':1.03,'net_income':4.965e9},
        ('AVGO','2026-05-03'):{'diluted_eps':1.91},
        ('AVGO','2024-08-04'):{'net_income':-1.875e9,'diluted_eps':-0.4},
        ('NVDA','2024-04-28'):{'available_as_of':'2024-05-23','share_basis':None},
        ('NVDA','2026-04-26'):{'free_cash_flow':48.554e9},
        ('UNH','2025-03-31'):{'available_as_of':'2025-04-18','diluted_eps':6.85},
        ('UNH','2025-06-30'):{'diluted_eps':3.74,'net_income':3.406e9},
        ('ORCL','2025-05-31'):{'net_income':3.427e9,'diluted_eps':1.19},
        ('COST','2025-05-11'):{'net_income':1.903e9,'diluted_eps':4.28,'free_cash_flow':2.329e9},
        ('COST','2025-08-31'):{'revenue':86.156e9,'net_income':2.610e9,'diluted_eps':5.87,'free_cash_flow':1.901e9},
        ('COST','2025-02-16'):{'free_cash_flow':1.611e9},
        ('COST','2025-11-23'):{'free_cash_flow':3.162e9,'total_equity':30.303e9},
        ('COST','2026-02-15'):{'free_cash_flow':1.707e9},
        ('COST','2026-05-10'):{'free_cash_flow':2.036e9,'total_equity':33.509e9},
        ('TSM','2025-06-30'):{'diluted_eps':2.47,'diluted_eps_currency':'USD','currency':'TWD','share_basis':'TSM-ADR','free_cash_flow':199.85e9},
    }
    checks=0
    for key,expected in golden.items():
        for field,value in expected.items():
            actual=records[key].get(field)
            assert math.isclose(actual,value,rel_tol=1e-12) if isinstance(value,(int,float)) else actual==value,(key,field,actual,value)
            checks+=1
    print(f'PASS: {checked} fiscal observations; {len(sources)} source hashes; {checks} issuer golden checks')


if __name__=='__main__':validate()
