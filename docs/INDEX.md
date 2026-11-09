# AI Stock Analysis Documentation Index

This index routes durable project knowledge. Read only the documents relevant to the task, then inspect their code owners. Paths in topic documents are relative to the repository root unless stated otherwise.

## Start here

| Task | Owner to read |
|---|---|
| Shared agent constraints | [AGENTS.md](../AGENTS.md) |
| Setup, CLI usage and product workflows | [README](../README.md), [development](development.md) |
| Pipeline shape and generated overview | [architecture](../architecture.md), [pipeline.json](../pipeline.json) |
| Data, agent, synthesis, memory and API invariants | [Pipeline guide](pipeline-guide.md) |
| Backtests and portfolio comparisons | [Backtesting](backtesting.md) |
| Filing retrieval and historical visibility | [Filing RAG contract](design/filings-rag.md) |
| Input isolation and run execution | [Input execution contract](design/pipeline-input-execution-contract.md) |
| Historical fundamentals | [Historical evidence contract](design/historical-fundamental-evidence.md) |
| Momentum system | [Standalone momentum](design/momentum-standalone.md), [reference context](design/momentum-reference-context.md) |
| Portfolio research and forward validation | [Portfolio pipeline](design/portfolio-pipeline-upgrade.md), [forward validation](design/pipeline-forward-validation-v2.md) |
| Deployment and storage | [Deployment](deployment.md), [Supabase](supabase.md) |

## Source-of-truth map

| Information | Canonical owner | Consumers |
|---|---|---|
| Shared repository instructions | `AGENTS.md` | Claude entry point and other agents |
| Pipeline topology | `pipeline.json` | Architecture generator and dashboard diagram |
| Model defaults and runtime settings | `src/stock_analysis/config.py` | Pipeline and CLI |
| Python dependencies and CLI entry points | `pyproject.toml` | Installation and commands |
| Storage behavior | `src/stock_analysis/data/store.py` | Data ingestion and analysis |
| Public research snapshots | Configured analysis storage | API, screener and research tools |
| Historical findings | `docs/analysis/`, `reports/analysis/` | Research evidence; inspect dates and assumptions before citing |
| Design intent | `docs/design/` | Implementation work; verify status against code |

## Maintenance

Update the owning document and its live references when a contract changes. Keep generated architecture in its existing root owner. Add new durable topics here; do not duplicate research results or replace historical evidence with current conclusions. Commands and schemas are defined by their manifests and source code, not copied examples.
