"""Extract source-linked issuer observations; never read outcomes or forecasts."""
from __future__ import annotations
from datetime import date, datetime, timedelta
from hashlib import sha256
from io import StringIO
import calendar
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pandas as pd
from pypdf import PdfReader
from stock_analysis.models.market_data import FinancialStatements

HERE = Path(__file__).resolve().parent
MONTHS = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)'
DATE = rf'{MONTHS}\s+\d{{1,2}},?\s+20\d{{2}}'
NUMBER = r'\(?-?\d[\d,]*(?:\.\d+)?\)?'

def dt(s):
    s = s.replace(',', '').replace('.', '').replace('Sept ', 'Sep ')
    for fmt in ['%B %d %Y','%b %d %Y']:
        try: return datetime.strptime(s.strip(), fmt).date()
        except ValueError: pass
    raise ValueError('Invalid source date '+s)

def number(s):
    s = s.replace('$','').replace(',','').replace('%','').strip()
    return -float(s.strip('()')) if s.startswith('(') else float(s.rstrip(')'))

def compact(s): return re.sub(r'\s+', ' ', str(s).replace('\x00','').replace('\u200b',' ')).strip()

def vals(s):
    # Percentages are not amounts and must not shift a monetary column.
    s = re.sub(r'\(?-?\d[\d,.]*%\)?', '', s)
    s = re.sub(r'(?<!\S)[—–-](?!\S)', '0', s)
    return [number(x) for x in re.findall(NUMBER,s)]

def rows(table):
    result=[]
    for _, row in table.iterrows():
        cells=[compact(v) for v in row.tolist() if pd.notna(v)]
        if not cells: continue
        result.append((cells[0].lower(), vals(' '.join(cells[1:])), ' | '.join(cells)))
    return result

def field(rs, names, index=0, last=False):
    matches=[(v,line) for name,v,line in rs if name in names and len(v)>index]
    if not matches:return None,None
    v,line=matches[-1] if last else matches[0]
    return v[index],line

def pdf_lines(text):
    return [compact(x) for x in text.splitlines() if compact(x)]

def pdf_field(lines, pattern):
    for line in lines:
        match=re.match(pattern,line,re.I)
        if match:
            v=vals(line[match.end():].replace('................................................................',' '))
            if v: return v[0],line
    return None,None

def make(source, start, end, released, fields, evidence, currency='USD', basis=None, eps_currency=None):
    assert released >= end, (source['id'],released,end)
    provenance={name:{'url':source['url'],'source_sha256':source['sha256'],
                       'source_file':source['path'],'released':released.isoformat(),
                       'selector_or_excerpt':evidence.get(name,'derived from cited same-period observations'),
                       'scale':'currency units; EPS per declared share basis'} for name,v in fields.items() if v is not None}
    record=dict(ticker=source['ticker'],fiscal_period_start=start.isoformat(),fiscal_period_end=end.isoformat(),
                period_kind='quarter',available_as_of=(released+timedelta(days=1)).isoformat(),
                availability_source='issuer_earnings_release',currency=currency,share_basis=basis,
                diluted_eps_currency=eps_currency,fact_provenance=provenance,**fields)
    FinancialStatements.model_validate(record)
    return record

def html_source(source):
    html=(HERE/source['path']).read_text()
    soup=BeautifulSoup(html,'html.parser')
    text=compact(soup.get_text(' ',strip=True))
    tables=pd.read_html(StringIO(html))
    if source['ticker']=='AVGO':
        released=date.fromisoformat(soup.find('meta',attrs={'name':'date'})['content'][:10])
    else:
        marker=text.find('REDMOND') if source['ticker']=='MSFT' else text.find('NVIDIA (NASDAQ: NVDA)')
        dates=re.findall(DATE,text[max(0,marker-200):marker+600])
        if source['ticker']=='MSFT':released=dt(dates[0])
        else:
            # The newsroom dateline immediately precedes the release body.
            released=dt(re.findall(DATE,text[:marker])[0])
    end=dt(re.search(r'\bended\s+('+DATE+r')',text,re.I)[1])
    if source['ticker']=='MSFT':
        start=date(end.year,((end.month-1)//3)*3+1,1)
    else:
        start=end-timedelta(days=90)
    if source['ticker']=='NVDA':
        inc=next(t for t in tables if 'CONDENSED CONSOLIDATED STATEMENTS OF INCOME' in t.to_string())
    elif source['ticker']=='MSFT':
        inc=next(t for t in tables if 'Total  revenue' in t.to_string() or 'Total revenue' in t.to_string())
    else:
        inc=next(t for t in tables if 'CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS' in t.to_string())
    rs=rows(inc);fields={};evidence={}
    names={'revenue':{'revenue','total revenue','net revenue'},'net_income':{'net income','net income (loss)','net loss'},'diluted_eps':({'net income per share','net income (loss) per share','net loss per share'} if source['ticker']=='AVGO' else {'diluted'})}
    for key,labels in names.items():
        if source['ticker']=='AVGO' and key=='diluted_eps':
            value,line=field(rs,labels,last=True)
            if value is None: value,line=field(rs,{'diluted'})
        else:value,line=field(rs,labels)
        fields[key]=value if key=='diluted_eps' or value is None else value*1e6;evidence[key]=line
    for key,labels in [('cost',{'cost of revenue','total cost of revenue'}),('operating',{'operating income'})]:
        value,line=field(rs,{'total cost of revenue'} if key=='cost' else labels)
        if value is None:value,line=field(rs,labels)
        if value is not None and fields['revenue']:
            output='gross_margin' if key=='cost' else 'operating_margin'
            fields[output]=(1-value*1e6/fields['revenue']) if key=='cost' else value*1e6/fields['revenue'];evidence[output]=line
    fields['net_margin']=fields['net_income']/fields['revenue'] if fields['net_income'] is not None and fields['revenue'] else None
    # Only tables explicitly carrying quarterly cash-flow columns qualify.
    for table in tables:
        st=compact(table.to_string()).lower()
        if ('cash flows' in st or 'net cash provided by operating activities' in st) and ('three months ended' in st or 'fiscal quarter ended' in st):
            cash=rows(table)
            ocf,line1=field(cash,{'net cash provided by operating activities','net cash from operations'})
            capex,line2=field(cash,{'purchase related to property and equipment and intangible assets','purchases related to property and equipment and intangible assets','purchases of property, plant and equipment','additions to property and equipment'})
            if ocf is not None and capex is not None:
                principal,l3=field(cash,{'principal payments on property and equipment and intangible assets'}) if source['ticker']=='NVDA' else (None,None)
                fields['free_cash_flow']=(ocf-abs(capex)-abs(principal or 0))*1e6;evidence['free_cash_flow']=str(line1)+'; '+str(line2)+'; '+str(l3);break
    if source['ticker']=='MSFT':
        # Its tables use column headers rather than repeated header rows.
        cash=next((t for t in tables if 'Additions  to property and equipment' in t.to_string()),None)
        if cash is not None and 'Three Months Ended' in str(cash.columns):
            cr=rows(cash);ocf,l1=field(cr,{'net cash from operations'});capex,l2=field(cr,{'additions to property and equipment'})
            if ocf is not None and capex is not None:fields['free_cash_flow']=(ocf-abs(capex))*1e6;evidence['free_cash_flow']=str(l1)+'; '+str(l2)
    # Diluted weighted-average shares are not period-end shares outstanding.
    basis={'NVDA':'NVDA-common-post-2024-06-07-split','AVGO':'AVGO-common-post-2024-07-15-split','MSFT':'MSFT-common'}[source['ticker']]
    if source['ticker']=='NVDA' and source['id']=='fy2025q1':basis=None
    # A balance sheet's leading column must match the income quarter end.
    for table in tables:
        st=compact(table.to_string())
        if 'BALANCE SHEET' not in st.upper():continue
        br=rows(table)
        # Repeated multi-column headings can split month/day and year across rows.
        date_prefix=end.strftime('%B')+' '+str(end.day)+','
        if date_prefix not in st or str(end.year) not in st:continue
        eq,le=field(br,{"shareholders' equity","total shareholders' equity","total stockholders' equity"})
        debt,ld=field(br,{'long-term debt'})
        short,ls=field(br,{'short-term debt'})
        if eq is not None:fields['total_equity']=eq*1e6;evidence['total_equity']=le
        if debt is not None:
            fields['total_debt']=(debt+(short or 0))*1e6
            fields['debt_scope']='reported_total' if short is not None else 'matched_long_term_subtotal'
            evidence['total_debt']=str(ld)+'; '+str(ls)
        break
    assert fields['revenue'] is not None and fields['diluted_eps'] is not None,(source['id'],fields)
    return make(source,start,end,released,fields,evidence,basis=basis)

def pdf_source(source):
    reader=PdfReader(HERE/source['path'])
    pages=[p.extract_text(extraction_mode='layout') for p in reader.pages]
    text='\n'.join(pages);lines=pdf_lines(text);norm=compact(text)
    (HERE/source['path']).with_suffix('.txt').write_text(text)
    t=source['ticker'];fields={};evidence={}
    if t=='TSM':
        released=dt(re.findall(DATE,norm)[0]);end=dt(re.search(r'quarter ended ('+DATE+r')',norm,re.I)[1]);start=date(end.year,((end.month-1)//3)*3+1,1)
        for key,pattern,mult in [('revenue',r'consolidated revenue of NT\$([\d,.]+) billion',1e9),('net_income',r'net income of NT\s*\$\s*([\d,.]+) billion',1e9),('diluted_eps',r'diluted earnings per share of NT\s*\$\s*([\d,.]+)',1)]:
            match=re.search(pattern,norm,re.I);assert match,(source['id'],key);fields[key]=number(match[1])*mult;evidence[key]=match[0]
        for key,pattern in [('gross_margin',r'Gross margin for the quarter was ([\d.]+)%'),('operating_margin',r'operating margin was ([\d.]+)%'),('net_margin',r'net profit margin was ([\d.]+)%')]:
            match=re.search(pattern,norm,re.I)
            if match:fields[key]=float(match[1])/100;evidence[key]=match[0]
        adr=re.search(r'US\s*\$\s*([\d,.]+) per ADR',norm,re.I)
        assert adr,(source['id'],'USD ADR EPS')
        evidence['diluted_eps']=adr[0]+'; native '+evidence['diluted_eps']
        fields['diluted_eps']=number(adr[1])
        return make(source,start,end,released,fields,evidence,currency='TWD',basis='TSM-ADR',eps_currency='USD')
    if t=='V':
        # Deck cover clocks and labelled GAAP summary; values explicitly rounded.
        released=dt(re.findall(DATE,norm)[0]);fy,q=map(int,re.match(r'fy(\d+)q(\d)',source['id']).groups());month=[12,3,6,9][q-1];year=fy-1 if q==1 else fy
        end=date(year,month,calendar.monthrange(year,month)[1]);start=date(year if month>2 else year-1,(month-3)%12+1,1)
        summary=next(compact(p) for p in pages if 'Income Statement Summary' in p)
        for key,label,mult in [('revenue','Net Revenue',1e9),('net_income','GAAP Net Income',1e9),('diluted_eps','GAAP Earnings Per Share',1)]:
            match=re.search(r'\b'+label+r'\s+\$([\d,.]+)',summary);assert match,(source['id'],key);fields[key]=number(match[1])*mult;evidence[key]=match[0]+' (issuer-rounded deck observation)'
        # Use actual GAAP net income/EPS from the quarterly reconciliation,
        # never its adjacent non-GAAP or fiscal-YTD columns.
        recon=next((p for p in pages if 'Reconciliation of GAAP to Non-GAAP Financial Results' in p and 'Three Months Ended' in p),None)
        if recon:
            actual,line=pdf_field(pdf_lines(recon),r'(?:GAAP|As reported)\s+')
            gaap_line=next(l for l in pdf_lines(recon) if re.match(r'(?:GAAP|As reported)\s+',l))
            values=vals(re.sub(r'^(?:GAAP|As reported)\s+','',gaap_line));assert len(values)>=4
            fields['net_income']=values[-2]*1e6;fields['diluted_eps']=values[-1]
            evidence['net_income']=gaap_line+'; current-quarter GAAP net income (penultimate monetary column)'
            evidence['diluted_eps']=gaap_line+'; current-quarter GAAP diluted EPS (final monetary column)'
        cash=next((compact(p) for p in pages if 'Calculation of Free Cash Flow' in p),None)
        if cash:
            match=re.search(r'Free cash flow\s*\(?1\)?\s*\$?\s*([\d,]+)',cash,re.I)
            if match:
                fields['free_cash_flow']=number(match[1])*1e6;evidence['free_cash_flow']=match[0]+'; first current-quarter column, USD millions'
        fields['net_margin']=fields['net_income']/fields['revenue']
        return make(source,start,end,released,fields,evidence,basis='V-Class-A')
    if t=='COST':
        # Date and fiscal duration in the original issuer announcement.
        released=date.fromisoformat(re.findall(r'20\d{2}-\d{2}-\d{2}',norm)[0]) if re.search(r'20\d{2}-\d{2}-\d{2}',norm) else dt(re.findall(DATE,norm)[0])
        end=dt(re.search(r'\bended ('+DATE+r')',norm,re.I)[1]);weeks=16 if '16-week fourth quarter' in norm else 12
        start=end-timedelta(days=weeks*7-1)
        statement_index=next(i for i,p in enumerate(pages) if 'STATEMENTS OF INCOME' in p)
        lines=pdf_lines('\n'.join(pages[statement_index:]))
        for key,pattern in [('revenue',r'(?:OPERATING EXPENSES)?Total revenue\s*'),('net_income',r'NET INCOME\s*'),('diluted_eps',r'Diluted\s*')]:
            value,line=pdf_field(lines,pattern);assert value is not None,(source['id'],key);fields[key]=value*(1 if key=='diluted_eps' else 1e6);evidence[key]=line
        value,line=pdf_field(lines,r'Operating income\s*')
        if value is not None:fields['operating_margin']=value*1e6/fields['revenue'];evidence['operating_margin']=line
        fields['net_margin']=fields['net_income']/fields['revenue']
        return make(source,start,end,released,fields,evidence,basis='COST-common')
    if t=='UNH':
        cover=compact(reader.pages[0].extract_text()).replace('J uly','July').replace('A pril','April')
        released=dt(re.findall(DATE,cover)[0])
        op=next(p for p in pages if 'CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS' in p)
        # Quarterly column clock is declared by the statement heading.
        fy=released.year;quarter=4 if released.month==1 else (released.month-1)//3
        year=fy-1 if quarter==4 else fy;month=quarter*3
        end=date(year,month,calendar.monthrange(year,month)[1]);start=date(year if month>2 else year-1,(month-3)%12+1,1)
        ls=pdf_lines(op)
        for key,pattern in [('revenue',r'Total revenues\s*\.*\s*'),('net_income',r'Net (?:earnings|\(loss\) earnings|earnings \(loss\)) attributable to UnitedHealth Group common shareholders\s*\.*\s*')]:
            value,line=pdf_field(ls,pattern);assert value is not None,(source['id'],key);fields[key]=value*1e6;evidence[key]=line
        # The reconciliation repeats actual GAAP diluted EPS, then adjusted EPS.
        joined=re.sub(r'common\s+shareholders', 'common shareholders', op)
        value,line=pdf_field(pdf_lines(joined),r'Diluted (?:earnings|\(loss\) earnings|earnings \(loss\)) per share(?: attributable to UnitedHealth Group common shareholders)?\s*\.*\s*')
        assert value is not None,(source['id'],'EPS');fields['diluted_eps']=value;evidence['diluted_eps']=line
        value,line=pdf_field(ls,r'Earnings from operations\s*\.*\s*')
        if value is not None:fields['operating_margin']=value*1e6/fields['revenue'];evidence['operating_margin']=line
        fields['net_margin']=fields['net_income']/fields['revenue']
        return make(source,start,end,released,fields,evidence,basis='UNH-common')
    if t=='ORCL':
        statement=next(p for p in pages if 'CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS' in p and 'NON-GAAP' not in p)
        lines=pdf_lines(statement)
        released=dt(re.findall(DATE,norm)[0]);fy,q=map(int,re.match(r'fy(\d+)q(\d)',source['id']).groups());month=[8,11,2,5][q-1];year=fy-1 if q<=2 else fy
        end=date(year,month,calendar.monthrange(year,month)[1]);start=date(year if month>2 else year-1,(month-3)%12+1,1)
        for key,pattern in [('revenue',r'Total revenues\s*'),('net_income',r'NET INCOME\s*'),('diluted_eps',r'Diluted\s*')]:
            value,line=pdf_field(lines,pattern);assert value is not None,(source['id'],key);fields[key]=value*(1 if key=='diluted_eps' else 1e6);evidence[key]=line
        fields['net_margin']=fields['net_income']/fields['revenue']
        return make(source,start,end,released,fields,evidence,basis='ORCL-common')
    raise ValueError(t)

def oracle_narrative(source):
    soup=BeautifulSoup((HERE/source['path']).read_text(),'html.parser')
    text=compact(soup.get_text(' ',strip=True))
    dateline=re.search(r'(?:Austin|AUSTIN),? Texas[—, ]+('+DATE+r')',text)
    if not dateline:
        dateline=re.search(DATE,text)
        released=dt(dateline[0])
    else:released=dt(dateline[1])
    fy,q=map(int,re.match(r'fy(\d+)q(\d)',source['id']).groups());month=[8,11,2,5][q-1];year=fy-1 if q<=2 else fy
    end=date(year,month,calendar.monthrange(year,month)[1]);start=date(year if month>2 else year-1,(month-3)%12+1,1)
    fields={};evidence={}
    patterns={
      'revenue':rf'Q{q} Total Revenue(?:s)?\s*\$\s*([\d.]+) billion',
      'net_income':r'(?<!Non-)(?<!non-)GAAP net income(?: available to common shareholders)? (?:was|of|reached)\s*\$\s*([\d.]+) billion',
      'diluted_eps':r'(?<!Non-)(?<!non-)GAAP [Ee]arnings per [Ss]hare(?: (?:was|of|up [\d%]+ to|increased to))?\s*\$\s*([\d.]+)',
    }
    for key,pattern in patterns.items():
        match=re.search(pattern,text)
        assert match,(source['id'],key)
        fields[key]=float(match[1])*(1 if key=='diluted_eps' else 1e9);evidence[key]=match[0]+' (issuer-rounded narrative observation)'
    fields['net_margin']=fields['net_income']/fields['revenue']
    return make(source,start,end,released,fields,evidence,basis='ORCL-common')


def enrich_pdf_balance_cash(series, manifest):
    cumulative={}
    for source in manifest['sources']:
        t=source['ticker']
        if t not in {'COST','UNH'} or source['status']=='failed' or not source['path'].endswith('.pdf'):continue
        records=[r for r in series[t] if any(v.get('source_file')==source['path'] for v in r['fact_provenance'].values())]
        if not records:continue
        target=max(records,key=lambda r:r['fiscal_period_end']);end=date.fromisoformat(target['fiscal_period_end'])
        pages=[p.extract_text() if t=='COST' else p.extract_text(extraction_mode='layout') for p in PdfReader(HERE/source['path']).pages]
        whole='\n'.join(pages)
        balance_index=next((i for i,p in enumerate(pages) if 'BALANCE SHEETS' in p),None)
        if balance_index is not None:
            balance='\n'.join(pages[balance_index:])
            ls=pdf_lines(balance)
            patterns={'total_equity':(r'TOTAL EQUITY\s*' if t=='COST' else r'Equity\s*\.*\s*'),
                'long_debt':r'(?:OTHER LIABILITIES)?Long-term debt(?:, excluding current portion|, less current maturities)\s*\.*\s*',
                'short_debt':r'Short-term borrowings and current maturities of long-term debt\s*\.*\s*'}
            found={k:pdf_field(ls,p) for k,p in patterns.items()}
            value,line=found['total_equity']
            if value is not None:
                target['total_equity']=value*1e6
                target['fact_provenance']['total_equity']=pdf_provenance(source,target,line)
            debt,ld=found['long_debt'];short,sd=found['short_debt']
            if debt is not None:
                target['total_debt']=(debt+(short or 0))*1e6
                target['debt_scope']='reported_total' if short is not None else 'matched_long_term_subtotal'
                target['fact_provenance']['total_debt']=pdf_provenance(source,target,str(ld)+'; '+str(sd))
        cash_index=next((i for i,p in enumerate(pages) if 'STATEMENTS OF CASH FLOWS' in p),None)
        if cash_index is None:continue
        cash='\n'.join(pages[cash_index:]);ls=pdf_lines(cash)
        ocf,lo=pdf_field(ls,r'Net cash provided by operating activities\s*' if t=='COST' else r'Cash flows from operating activities\s*\.*\s*')
        capex,lc=pdf_field(ls,r'(?:Additions to property and equipment|Purchases of property, equipment and capitalized software)\s*\.*\s*')
        if ocf is None or capex is None:continue
        if t=='UNH':
            start=date(end.year,1,1)
            duration={3:'Three',6:'Six',9:'Nine',12:'Twelve'}[end.month]+' Months Ended'
            if end.month==12 and 'Year Ended' in cash:duration='Year Ended'
            assert duration.lower() in compact(cash).lower(),(source['id'],'cash duration')
        else:
            match=re.search(r'(12|24|36|52|53) Weeks Ended',compact(cash));assert match,(source['id'],'cash duration')
            start=end-timedelta(days=int(match[1])*7-1)
        cumulative[(t,start,end)]=(ocf-abs(capex))*1e6,source,target,lo+'; '+lc
    for (t,start,end),(value,source,target,excerpt) in cumulative.items():
        quarter_start=date.fromisoformat(target['fiscal_period_start'])
        if quarter_start==start:
            target['free_cash_flow']=value
            target['fact_provenance']['free_cash_flow']=pdf_provenance(source,target,excerpt+'; quarter cash duration')
        elif (t,start,quarter_start-timedelta(days=1)) in cumulative:
            previous=cumulative[(t,start,quarter_start-timedelta(days=1))]
            assert previous[2]['available_as_of']<=target['available_as_of']
            target['free_cash_flow']=value-previous[0]
            provenance=pdf_provenance(source,target,excerpt+'; quarter = current fiscal-YTD minus preceding fiscal-YTD')
            provenance['preceding_ytd_source']=pdf_provenance(previous[1],previous[2],previous[3])
            provenance['fiscal_ytd_start']=start.isoformat()
            target['fact_provenance']['free_cash_flow']=provenance


def pdf_provenance(source, target, excerpt):
    return {'url':source['url'],'source_file':source['path'],'source_sha256':source['sha256'],
        'released':(date.fromisoformat(target['available_as_of'])-timedelta(days=1)).isoformat(),
        'selector_or_excerpt':excerpt,'scale':'USD millions x 1e6'}


def enrich_tsm_management(series, manifest):
    for source in manifest['sources']:
        if source['ticker']!='TSM' or not source['id'].endswith('-management') or source['status']=='failed':continue
        text=compact(' '.join(p.extract_text() for p in PdfReader(HERE/source['path']).pages))
        matches=list(re.finditer(r'Free cash flow (?:increased|decreased|was|reached).{0,200}',text,re.I))
        if not matches:continue
        excerpt=matches[-1][0]
        amount=re.search(r'(?:to (?:an inflow of )?|was |reached )NT\s*\$\s*([\d,.]+) billion',excerpt,re.I)
        if not amount:continue
        year,q=map(int,re.match(r'(\d+)q(\d)',source['id']).groups())
        end=date(year,q*3,calendar.monthrange(year,q*3)[1]).isoformat()
        target=next(r for r in series['TSM'] if r['fiscal_period_end']==end)
        released=dt(re.findall(DATE,text)[0]);assert (released+timedelta(days=1)).isoformat()==target['available_as_of']
        target['free_cash_flow']=number(amount[1])*1e9
        target['fact_provenance']['free_cash_flow']={'url':source['url'],'source_sha256':source['sha256'],
            'source_file':source['path'],'released':released.isoformat(),'selector_or_excerpt':excerpt,'scale':'NT$ billion x 1e9; current quarter narrative'}


def comparative(source, current):
    """Three missing year-ago quarters explicitly printed beside current GAAP results."""
    key=(source['ticker'],source['id'])
    spec={('AVGO','fy2025q2'):(date(2024,5,5),91,2),
          ('COST','fy2025q3'):(date(2024,5,12),84,1),
          ('ORCL','fy2025q4'):(date(2024,5,31),92,1)}
    if key not in spec:return None
    end,days,column=spec[key];fields={};evidence={}
    if key[0]=='AVGO':
        tables=pd.read_html(StringIO((HERE/source['path']).read_text()))
        table=next(t for t in tables if 'CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS' in t.to_string())
        rs=rows(table)
        labels={'revenue':{'net revenue'},'net_income':{'net income'},'diluted_eps':{'net income per share'}}
        for name,names in labels.items():
            value,line=field(rs,names,index=column,last=name=='diluted_eps')
            assert value is not None
            fields[name]=value*(1 if name=='diluted_eps' else 1e6);evidence[name]=line+'; year-ago column '+str(column)
    else:
        pages=[p.extract_text(extraction_mode='layout') for p in PdfReader(HERE/source['path']).pages]
        marker='STATEMENTS OF INCOME' if key[0]=='COST' else 'CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS'
        statement=next(p for p in pages if marker in p and 'NON-GAAP' not in p)
        patterns={'revenue':r'(?:OPERATING EXPENSES)?Total revenue[s]?\s*','net_income':r'NET INCOME\s*','diluted_eps':r'Diluted\s*'}
        for name,pattern in patterns.items():
            _,line=pdf_field(pdf_lines(statement),pattern);assert line
            match=re.match(pattern,line,re.I);values=vals(line[match.end():]);assert len(values)>column
            fields[name]=values[column]*(1 if name=='diluted_eps' else 1e6);evidence[name]=line+'; year-ago column '+str(column)
    fields['net_margin']=fields['net_income']/fields['revenue']
    released=date.fromisoformat(current['available_as_of'])-timedelta(days=1)
    return make(source,end-timedelta(days=days-1),end,released,fields,evidence,basis=current['share_basis'])


def main():
    manifest=json.loads((HERE/'download-manifest.json').read_text());series={t:[] for t in ['NVDA','MSFT','AVGO','TSM','V','UNH','ORCL','COST']};errors=[]
    for source in manifest['sources']:
        if source['status']=='failed' or source['id']=='index':continue
        t=source['ticker'];p=HERE/source['path']
        if t=='TSM' and not source['id'].endswith('-earnings'):continue
        if t=='UNH' and ('8' in source['id'].lower() or 'form' in source['id'].lower() or 'reconciliation' in source['id'].lower()):continue
        try:
            record=oracle_narrative(source) if t=='ORCL' and p.suffix=='.html' else html_source(source) if p.suffix=='.html' else pdf_source(source)
            series[t].append(record)
            prior=comparative(source,record)
            if prior:series[t].append(prior)
        except (ValueError,AssertionError,KeyError,IndexError,StopIteration,TypeError) as exc:
            errors.append({'ticker':t,'id':source['id'],'error':str(exc)[:400]})
    enrich_tsm_management(series,manifest)
    enrich_pdf_balance_cash(series,manifest)
    (HERE/'extracted.json').write_text(json.dumps(series,indent=2)+'\n')
    (HERE/'extraction-errors.json').write_text(json.dumps(errors,indent=2)+'\n')
    print('Extracted', {t:len(rs) for t,rs in series.items()})
    print('Errors',errors)
if __name__=='__main__':main()
