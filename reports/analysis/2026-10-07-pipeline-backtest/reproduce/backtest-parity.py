import json,hashlib
from datetime import datetime,timezone
from pathlib import Path
from stock_analysis.models.agent_reports import AnalystReports,Signal
from stock_analysis.backtest.session import SessionPrediction
from stock_analysis.synthesis.synthesizer import compute_directional_consensus,compute_signal_convergence,calibrate_conviction_score
from stock_analysis.synthesis.risk_checker import is_actionable
R=Path('reports/analysis/2026-10-07-pipeline-backtest');S=R/'session'
inputs=json.loads((R/'inputs-compact.json').read_text()); roles={}
for role in ['fundamentals','sentiment','technical','macro']:
 roles[role]={(x['ticker'],x['as_of_date']):x['report'] for x in json.loads((R/f'{role}-reports.json').read_text())}
synth={(x['ticker'],x['as_of_date']):x for x in json.loads((R/'synthesis-reports.json').read_text())}
pred=[]; parity=[]
for x in inputs:
 k=x['ticker'],x['as_of_date']; a=AnalystReports.model_validate({role:rows[k] for role,rows in roles.items()}); syn=synth[k]; signal=Signal(syn['overall_signal']);raw=syn['conviction_score']
 consensus=compute_directional_consensus(a);convergence=compute_signal_convergence(a)
 p=SessionPrediction(ticker=k[0],as_of_date=k[1],overall_signal=signal,conviction_score=raw,signal_convergence=convergence,agent_signals={r:getattr(a,r).signal for r in roles},agent_confidences={r:getattr(a,r).confidence for r in roles});pred.append(p.model_dump(mode='json'))
 score=calibrate_conviction_score(signal,raw,consensus); final=signal if signal==Signal.NEUTRAL or is_actionable(score,convergence) else Signal.NEUTRAL
 parity.append(dict(ticker=k[0],as_of_date=k[1],raw_signal=signal.value,raw_score=raw,consensus=consensus,signal_convergence=convergence,conviction_score=score,overall_signal=final.value))
assert len(pred)==len(synth)==96
(S/'predictions.json').write_text(json.dumps(pred,indent=2)+'\n');(R/'production-parity-predictions.json').write_text(json.dumps(parity,indent=2)+'\n')
files=list((S/'packets').rglob('*.json'))+[S/'manifest.json',S/'predictions.json',R/'production-parity-predictions.json',R/'protocol.json',R/'method.json',R/'synthesis-reports.json',R/'debate-reports.json']+[R/f'{r}-reports.json' for r in roles]
(R/'seal.json').write_text(json.dumps({'sealed_at_utc':datetime.now(timezone.utc).isoformat(),'stage':'before_any_forward_scoring','prediction_count':96,'files':{str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}},indent=2)+'\n')
from collections import Counter
print('Raw',Counter(x['overall_signal'] for x in pred));print('Production parity',Counter(x['overall_signal'] for x in parity));print('Sealed',len(files),'files')
