import json
from pathlib import Path
from stock_analysis.backtest.session import SessionPrediction,calibrate_session_prediction
from stock_analysis.synthesis.synthesizer import calibrate_conviction_score
from stock_analysis.synthesis.risk_checker import is_actionable
from stock_analysis.models.agent_reports import Signal
p=SessionPrediction(ticker='EXAMPLE',as_of_date='2025-09-01',overall_signal='buy',conviction_score=.2,signal_convergence=.6,agent_signals={'fundamentals':'buy','technical':'buy','macro':'neutral','sentiment':'neutral'},agent_confidences={'fundamentals':'medium','technical':'medium','macro':'low','sentiment':'low'})
s=calibrate_session_prediction(p)
prod=calibrate_conviction_score(Signal.BUY,.2,s.conviction_score)
assert s.overall_signal==Signal.BUY and not is_actionable(prod,s.signal_convergence)
Path('reports/analysis/2026-10-07-pipeline-backtest/parity-counterexample.json').write_text(json.dumps({'synthetic_unit_example_not_real_trial':True,'raw_model_score':.2,'consensus':s.conviction_score,'convergence':s.signal_convergence,'session_signal':s.overall_signal.value,'session_score':s.conviction_score,'production_score':prod,'production_actionable':is_actionable(prod,s.signal_convergence)},indent=2)+'\n')
print('Real functions reproduce parity difference: session buy at0.6; production0.2 fails execution.')
