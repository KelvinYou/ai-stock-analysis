# AI Stock Analysis — Architecture

Single-ticker analysis produces a guarded briefing. An optional completed-run
batch feeds deterministic portfolio research through `/api/v1/portfolio-plans`:
12-month/top-three allocation, nine signal/passive views and explicit cash.
The forward collector seals inputs before entry, refuses immature outcomes and
compares daily equity after costs. These outputs remain research-only; collection
requires a pinned prospective calendar and model/prompt provenance. See
[the upgrade contract](docs/design/portfolio-pipeline-upgrade.md).

```mermaid
flowchart TD

    subgraph L1["Layer 1 — Data Ingestion (Deterministic inputs — no LLM)"]
        UNI["Ticker universes<br/>S&amp;P 500 · NASDAQ 100 · FBM KLCI<br/>scraped from Wikipedia"]
        US["US market data<br/>yfinance · adjusted technical bars<br/>dated financial history · plain Close"]
        MY["Bursa / KLSE<br/>yfinance via .KL suffix<br/>BURSA_ALIASES name → code"]
        REPLAY["Historical replay<br/>SEC periods · revisions<br/>dated valuation basis<br/>API / session backtests"]
    end

    SDL["Analysis Store<br/>Supabase / local backend<br/>bars · dated evidence<br/>research artifacts · runs"]

    subgraph PREP["Layer 1.5 — Input Isolation (Deterministic evidence preparation)"]
        INPUT["Sealed run input<br/>dated evidence · recent news<br/>immutable SHA-256 · cloud resume"]
    end


    subgraph L2["Layer 2 — Analyst Agents (quick_think_model = Haiku)"]
        direction LR
        FUN["Fundamentals<br/>periods · growth · debt<br/>dated P/E · evidence gaps"]
        SEN["Sentiment<br/>news · analyst tone"]
        TEC["Technical<br/>RSI · MACD · volume"]
        MAC["Macro / FX<br/>Fed · rates · FX impact"]
    end


    subgraph L3["Layer 3 — Adversarial Debate (deep_think_model = Opus)"]
        direction LR
        BULL["Bull researcher<br/>best case · catalysts · upside"]
        BEAR["Bear researcher<br/>risks · headwinds · downside"]
    end


    subgraph L35["Layer 3.5 — Research Manager (research_manager_model = Sonnet)"]
        RM["ResearchManager<br/>winning side · thesis<br/>strongest counterexample<br/>invalidation conditions · evidence gaps"]
    end


    subgraph CTX["Supporting context — Outcome Memory (optional · resolved exits only)"]
        MEM["Outcome Memory<br/>cloud/local append-only outcomes<br/>hit rate · conviction calibration<br/>feeds context into synthesis"]
    end


    subgraph L4["Layer 4 — Synthesis (synthesis_model = Sonnet)"]
        SYN["SynthesizerAgent<br/>reports · debate · verdict<br/>optional outcome memory"]
        GATE["Consensus + actionability<br/>four-report denominator<br/>cap raw model conviction<br/>neutral is a valid result"]
        RISK["RiskChecker<br/>shared production/session gate<br/>finite positive ATR · ordered levels"]
    end


    subgraph L5["Layer 5 — Portfolio Research (optional completed-run batch · deterministic · US/USD)"]
        RANK["Run-bound allocator<br/>same-session sealed inputs<br/>12-month momentum · top three"]
        WEIGHTS["Nine target-weight views<br/>hold · allocator · FT · AI<br/>fixed sleeves · rejected signals keep cash"]
        COHORT["Forward cohort collector<br/>seal before entry · mature-only scoring<br/>daily equity · costs · paired uncertainty"]
    end


    OUT["Briefing<br/>conviction −1.00…+1.00<br/>entry · stop · targets · risk"]

    subgraph CONSUMERS["Consumers"]
        direction LR
        DASH["Next.js screener<br/>server-side FastAPI client<br/>one sortable row per ticker"]
        API["FastAPI<br/>analyze · completed run reads<br/>POST /api/v1/portfolio-plans"]
        BT["Backtester<br/>sealed replay · costs<br/>strict hold · uncertainty"]
    end

    UNI -.->|"bulk fetch"| US
    UNI -.->|"bulk fetch"| MY
    US --> SDL
    MY --> SDL
    REPLAY -.->|"historical inputs"| SDL
    INPUT --> L2
    L2 --> L3
    BULL <-->|"rebut · concede · refine"| BEAR
    L3 -.->|"enabled"| RM
    L2 -->|"reports"| SYN
    L3 -->|"debate"| SYN
    RM -.->|"verdict"| SYN
    MEM -.->|"resolved outcomes"| SYN
    SYN --> GATE
    GATE --> RISK
    RISK --> OUT
    OUT --> DASH
    OUT --> API
    OUT --> BT
    SDL -->|"freeze before analyst calls"| INPUT
    RISK -.->|"completed run panel"| RANK
    INPUT -.->|"same run snapshots"| RANK
    RANK --> WEIGHTS
    L2 -.->|"sealed FT reports"| WEIGHTS
    WEIGHTS -.->|"registered forward calendar"| COHORT
    WEIGHTS -.->|"portfolio plans"| API
    COHORT -.->|"nine-arm comparison"| BT

    style UNI fill:#fafaf9,stroke:#d6d3d1,color:#57534e
    style REPLAY fill:#fafaf9,stroke:#d6d3d1,color:#57534e
    style BULL fill:#dcfce7,stroke:#16a34a,color:#14532d
    style BEAR fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    style MEM fill:#fafaf9,stroke:#d6d3d1,color:#57534e
    style COHORT fill:#fafaf9,stroke:#d6d3d1,color:#57534e
    style OUT fill:#f5f5f4,stroke:#57534e,color:#1c1917
    style DASH fill:#fafaf9,stroke:#d6d3d1,color:#57534e
    style API fill:#fafaf9,stroke:#d6d3d1,color:#57534e
    style BT fill:#fafaf9,stroke:#d6d3d1,color:#57534e
```
