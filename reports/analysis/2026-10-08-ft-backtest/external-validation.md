# External Backtest Validation

**Overall: FAIL**

| Gate | Status | Observed | Requirement |
|---|---|---|---|
| point-in-time packet integrity | **FAIL** | fundamentals 55/96, sentiment 0/96 | technical, fundamentals, historical sentiment, and macro must be 100% covered |
| point-in-time metadata | **PASS** | 96 packet(s) fail-closed; 0 versioned packet(s) | use versioned historical metadata or omit unversioned company attributes |
| historical news source | **BLOCKED** | not_configured; SEC filing events are not a complete provider news feed | provider-versioned historical news coverage, with publication and first-available clocks |
| historical macro source | **PASS** | dated replay source(s): FRED:DFF; single-rate observation only | macro observations must carry observation and first-available dates |
| production provider run | **BLOCKED** | provider_run.json missing; current manifest is in-session | authenticated provider invocation bound to exact predictions and score |
| survivorship-safe universe | **BLOCKED** | universe.json missing; current fixed ticker list is not enough | hashed source extract and point-in-time membership for every trial |
| scored terminal-return provenance | **BLOCKED** | universe.json missing | scored returns must be tied to the declared total-return data hash |
| execution cost calibration | **BLOCKED** | cost_model.json missing; bps is only an assumption | externally calibrated spread, slippage, commission, and benchmark parity |
| scored panel completeness | **PASS** | 96/96 complete | one complete scored outcome per frozen (ticker, as-of) trial |
| effective sample | **FAIL** | invalid or missing overall portfolio effective_n=None | effective_n_basis=portfolio_overlap_clustered_v1 and portfolio effective n >= 30 |
| strict long-hold benchmark | **FAIL** | benchmark_beaten=False, promotion_ready=False | same window, universe, timing, and costs; pipeline must beat strict hold |
| paired strict-hold alpha interval | **FAIL** | 95% paired log-excess interval=[-0.0021, 0.0012] | lower 95% time-block-bootstrap bound of paired log excess must be > 0 |

PASS is emitted only when every gate is PASS. BLOCKED means an external artifact or authority is missing; FAIL means the supplied artifact does not satisfy the contract.

