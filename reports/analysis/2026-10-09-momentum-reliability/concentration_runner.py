from pathlib import Path
import json,math,hashlib
ROOT=Path('/Users/kelvin.you/Documents/dev/personal-os/repos/ai-stock-analysis')
OUT=ROOT/'reports/analysis/2026-10-09-momentum-reliability'
results={}
for panel in ['primary8','prior11','prior5']:
 src=OUT/f'{panel}-full-10bps.json';r=json.loads(src.read_text()); rows=[]
 for p in r['period_log']:
  rows.append({'as_of_date':p['as_of_date'],'selected_tickers':p['selected_tickers'],'candidate_net':p['net_return'],'hold_net':p['strict_hold_net_return'],'log_excess':math.log1p(p['net_return'])-math.log1p(p['strict_hold_net_return'])})
 total=sum(x['log_excess'] for x in rows)
 assert math.isclose(total,math.log1p(r['net_compound_return'])-math.log1p(r['buy_and_hold_return']),abs_tol=1e-10)
 ranked=sorted(rows,key=lambda x:x['log_excess'],reverse=True);positive=sum(max(x['log_excess'],0) for x in rows)
 cuts=[]
 for k in [1,3,5,10]:
  top=ranked[:k];remove={x['as_of_date'] for x in top};left=[x for x in rows if x['as_of_date'] not in remove]
  a=math.expm1(sum(math.log1p(x['candidate_net']) for x in left));b=math.expm1(sum(math.log1p(x['hold_net']) for x in left));cuts.append({'k':k,'positive_log_excess_share':sum(max(x['log_excess'],0) for x in top)/positive,'candidate_return_both_arms_omit_months':a,'hold_return_both_arms_omit_months':b,'remaining_log_excess':sum(x['log_excess'] for x in left),'top_months':top})
 counts={n:sum(n in x['selected_tickers'] for x in rows) for n in r['universe']}
 annual=[]
 for yr in sorted(set(x['as_of_date'][:4] for x in rows)):
  y=[x for x in rows if x['as_of_date'].startswith(yr)];annual.append({'signal_year':yr,'periods':len(y),'log_excess':sum(x['log_excess'] for x in y)})
 results[panel]={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'periods':len(rows),'winning_excess_months':sum(x['log_excess']>0 for x in rows),'total_log_excess':total,'total_relative_wealth_advantage':math.expm1(total),'positive_log_excess':positive,'cuts':cuts,'selection_frequency':counts,'annual_signal_date_log_excess':annual,'best_10':ranked[:10],'worst_10':ranked[-10:]}
(OUT/'concentration.json').write_text(json.dumps(results,indent=2)+'\n')
lines=['# Momentum return concentration — 2026-10-09','','[Status: Warning] Post-hoc sensitivity analysis on the same inspected history. No strategy or universe was changed.','','Contributions use additive paired monthly log excess versus continuous hold, including the benchmark entry/final-liquidation cost legs stored in the source report. Positive-contribution shares use the sum of positive log excess, not the signed net total. Removing months below omits those same intervals from both return series; it is an artificial diagnostic, not an executable strategy, fresh holdout, causal effect or forecast of expected returns. Ranking by realized excess uses hindsight.','','| Universe | Months beating hold | Relative terminal wealth advantage | Top 5 share of positive log excess | Log excess after omitting best 5 |','|---|---:|---:|---:|---:|']
for name,r in results.items():
 c=r['cuts'][2];lines.append(f"| {name} | {r['winning_excess_months']}/{r['periods']} | {r['total_relative_wealth_advantage']:.2%} | {c['positive_log_excess_share']:.2%} | {c['remaining_log_excess']:+.4f} |")
lines += ['','## Primary eight-name sensitivity','','| Best excess months omitted from both arms | Allocator return on remaining months | Hold return on remaining months | Remaining log excess |','|---|---:|---:|---:|']
for c in results['primary8']['cuts']:lines.append(f"| {c['k']} | {c['candidate_return_both_arms_omit_months']:.2%} | {c['hold_return_both_arms_omit_months']:.2%} | {c['remaining_log_excess']:+.4f} |")
lines += ['','## Primary strongest and weakest months','','| Signal date | Selected tickers | Paired log excess |','|---|---|---:|']
for x in results['primary8']['best_10'][:5]+list(reversed(results['primary8']['worst_10']))[:5]:lines.append(f"| {x['as_of_date']} | {', '.join(x['selected_tickers'])} | {x['log_excess']:+.4f} |")
lines += ['','Selection frequency measures exposure, not name-level causal P&L. Details, annual contributions and omitted-month rows for all three panels are in concentration.json. Exact reconciliation with original terminal relative wealth passed for all panels. Existing uncertainty, survivor-universe and return-source limitations remain unchanged.']
(OUT/'concentration.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines[:12]))
for panel,r in results.items(): print(panel,'best5_remaining',r['cuts'][2]['remaining_log_excess'],'best10_remaining',r['cuts'][3]['remaining_log_excess'])
