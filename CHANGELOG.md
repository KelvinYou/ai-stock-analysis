# Changelog

All notable changes to this project are recorded here. Versions follow
[Semantic Versioning](https://semver.org/) as defined for this repository in
[docs/development.md](docs/development.md#releases); every release states
whether its results are comparable with the previous version.

## [0.2.0] - 2026-11-28

### Results comparability

Not comparable with 0.1.0. Backtests now charge transaction costs and score
only signals that clear the execution gate; convergence is computed
deterministically with conviction capped by analyst consensus; macro,
sentiment and valuation inputs without dated evidence are left unavailable
instead of filled in; and live runs pass an evidence preflight gate. Rerun
0.1.0 backtests and briefings before comparing hit rates, returns or Sharpe
ratios with 0.2.0.

Adjusted price history is refreshed on the next fetch after a split or
dividend, instead of at the weekly resync.

### Added
- **fetch:** Narrow to explicit 10-ticker watchlist, drop universe scans
- **watchlist:** Make tickers.txt groups machine-readable
- **web:** Widen TickerSummary to what a screener needs
- **web:** Add a dense sortable table with at-entry / stale filters
- **web:** Make / the screener and state data freshness up front
- **web:** Render the pipeline as a flowchart from a single source of truth
- **backtest:** Add session mode to run backtests without an API key
- **pipeline:** Add research manager, portfolio gate, and outcome memory
- **web:** Type the trade decision and portfolio gate fields
- **backtest:** Add transaction cost modeling and stats module
- **web:** Add shareable ticker cards with QR + OG/twitter images
- Add Supabase cloud storage backend, factor backtesting, and watchlist
- **api:** Add production auth, admission quotas, worker leases, and public read API
- **web:** Switch dashboard reads to FastAPI public-data client
- **technicals:** Add historical indicator series for price charts
- **briefing:** Surface research verdict, fundamentals detail, and conviction map
- **web:** Narrow persistent nav chrome to a ticker summary projection
- **supabase:** Add sync verification for research_verdict stage
- **data:** Add bar-hygiene gate and briefing freshness/provenance tracking
- **backtest:** Add replay and experiment quality tools
- **pipeline:** Add portfolio cohort, dated evidence inputs and immutable run inputs
- **web:** Add allocation research view and pipeline description updates
- **allocation:** Add current allocation snapshot refresh
- **momentum:** Add standalone momentum dashboard pipeline
- **web:** Add momentum page and refresh allocation desk
- **filings:** Add SEC filings retrieval tool for the fundamentals agent
- **pipeline:** Add evidence preflight gate before live runs
- **backtest:** Add strategy comparison, pit fundamentals and current ranking
- **web:** Show current ranking, strategy comparison and trade log on allocation desk

### Fixed
- **integrity:** Stop fabricating macro/sentiment/valuation without dated evidence
- **synthesis:** Compute convergence deterministically, cap conviction by consensus
- **backtest:** Only score signals that clear the execution gate
- **api:** Keep a strong reference to in-flight analysis tasks
- **agents:** Lock down ClaudeAgentOptions to deny fs tools and bypass
- **web:** Disable fetch revalidation in dev so localhost reflects live data
- **web:** Stop pinning share metadata images for a year
- **web:** Use next/link for internal allocation link
- **fetch:** Refetch on dividends and drop the weekly full resync

### Performance
- **web:** Move price chart data prep to the server

### Changed
- **technical:** Use the single indicator implementation in data/technicals
- Drop the personal portfolio risk gate, relabel holdings as tracked tickers
- **web:** Drop group and change columns from ticker table
- **web:** Rebrand UI with fintech-minimal identity
- **web:** Rebrand UI with fintech-minimal design system
- **watchlist:** Drop tracked/candidate distinction, add MY:5126
- **web:** Read ticker browser filters from url without suspense

### Documentation
- Redesign README with screenshot, badges, and quick start
- Document session backtest usage and the TradingAgents comparison roadmap
- Document the new layers and fix storage-layout drift
- **backtest:** Document confidence intervals, cost modeling, and deflated Sharpe
- Collapse duplicate install instructions in README
- Document deployment/API auth and refresh pipeline diagram
- **analysis:** Add september backtest review
- Refresh pipeline contracts, CI, Postman and design notes
- **analysis:** Add 2026-10-07 and 2026-10-08 watchlist, cohort and backtest reports
- **analysis:** Add 2026-10-09 backtest rerun, momentum and pipeline diagnostics
- **analysis:** Add allocation revalidation and current allocation reports
- **analysis:** Add seven- and six-ticker refresh reports
- **analysis:** Add 2026-11-06 momentum reports
- **analysis:** Add 2026-11-08 filings RAG retrieval eval
- Add agent protocol, docs index and development guides
- **analysis:** Add 2026-11 ranking, strategy and fundamentals reports

### Maintenance
- Add MIT LICENSE
- **data:** Prune non-watchlist ticker directories
- **watchlist:** Expand tickers to 20, group by market and thesis
- Cover the signal-quality invariants
- **lint:** Pin the ruff rule set and clear it
- **data:** Refresh fetched briefings, add RKLB and Hextar (5151) tickers
- **data:** Refresh 6947 analyst reports, briefing, and debate result
- **config:** Ignore local env files and root vercel project link
- Add Docker image, compose stack, and CI contract checks
- **api:** Generate OpenAPI snapshot and Postman collection
- **web:** Switch lint to eslint cli and guard server-only modules
- **tickers:** Rebalance watchlist coverage
- **release:** Add git-cliff changelog and tag-driven releases

## [0.1.0] - 2026-04-19

### Results comparability

Baseline release.

### Added
- **models:** Add Pydantic data models for the full analysis pipeline
- **data:** Add market data ingestion layer with US and Malaysia fetchers
- **agents:** Add four specialist analyst agents (Layer 2)
- **debate:** Add adversarial bull/bear debate engine (Layer 3)
- **synthesis:** Add synthesis layer with risk checker and briefing synthesizer (Layer 4)
- **api:** Add FastAPI REST endpoints and CLI orchestrator
- **backtest:** Add backtesting framework to evaluate briefing accuracy
- **data:** Add technicals + flat per-ticker storage layout
- **web:** Next.js dashboard for ticker briefings
- **synthesis:** Attach concrete entry/stop/target levels to briefings
- **backtest:** Add portfolio simulation with position sizing
- **data:** Extend default price history to 10 years
- **web:** Redesign dashboard around a decision-first briefing
- **fetch:** Expand daily fetch to S&P 500 + Nasdaq 100 + FBMKLCI
- **web:** Client-side watchlist and recently-viewed tracking
- **web:** Landing page redesign and filterable dashboard browser

### Fixed
- **retry:** Bump SDK query retries to 5 with 3s backoff
- **fetch:** Wikipedia-compliant UA and non-fatal universe expansion
- **web:** Count agent agreement from prefixed signal strings
- **universe:** Wrap HTML in StringIO for pandas.read_html
- **web:** Cap summary fan-out to avoid EMFILE on serverless

### Changed
- **web:** Reorganize components by feature and split types

### Documentation
- Update README and architecture diagram to reflect current state

### Maintenance
- Initialize project with Python packaging and documentation
- **data:** Migrate MSFT snapshots to flat per-ticker layout
- Ignore local Claude Code tooling and runtime logs
- **data:** Add analyst, debate, and briefing snapshots for 7 tickers
- Add git-based versioning via hatch-vcs
