# TradingAgents 对比 + 修复路线图

日期: 2026-09-22
参考: [TradingAgents README](https://github.com/TauricResearch/TradingAgents/blob/main/README.md) · [graph/setup.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/setup.py) · [dataflows/market_data_validator.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/dataflows/market_data_validator.py) · [agents/utils/memory.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/agents/utils/memory.py) · [graph/reflection.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/reflection.py)

> **架构决策更新（2026-08-14）**：本文是历史对比/路线图。文中原先提出的
> `personal-os` portfolio gate 已被明确否决：这个 public repo 只输出股票研究，
> 不读取 private holdings；portfolio valuation、concentration 和 sizing 由 `personal-os`
> 自己负责。下文涉及该 gate 的旧建议以此边界为准。

> **Current status update (2026-09-22)**: The original P0 correctness list below is
> complete in code. This document remains a historical comparison, but the status
> notes have been updated so its old defect descriptions are not mistaken for
> current implementation gaps. The remaining work is evidence coverage and
> out-of-sample validation, not another prompt-only rewrite.

## 结论

**不整体迁移到 TradingAgents。** 本仓库的 deterministic 基础（typed backtest scorer、point-in-time fetcher、独立 RiskChecker）已经比 TradingAgents 文档描述的更严谨。当前 pipeline 的公共边界是"研究裁决 → 交易计划 → outcome memory"；portfolio gate 不属于这个 public repo。以下所有代码问题均已逐条对照源码核实（非转述猜测）。

---

## 1. 两边架构对比

| 维度 | TradingAgents | 本仓库 | 结论 |
|---|---|---|---|
| Analyst 团队 | 4 个，图内顺序执行 | 4 个，`asyncio.gather` 并行 (`orchestrator.py:64`) | 本仓库更快更省钱 |
| Debate | Bull/Bear，多轮 | Bull/Bear，多轮 (`debate/engine.py`) | 打平 |
| 研究裁决 | 有 Research Manager 汇总 debate | 有 `ResearchManager`（`debate/research_manager.py`） | 已补齐 |
| 交易执行层 | 独立 Trader agent 生成 entry/stop/target | `RiskChecker.plan_action()` deterministic 生成 (`risk_checker.py:114`) | 本仓库更可靠（非 LLM 捏造数字） |
| Portfolio Gate | Portfolio Manager 读真实持仓，approve/reject | **不属于本仓库**；private consumer 自己处理组合规则 | 保持 public/private 隔离 |
| 跨次记忆/reflection | 持久化 decision memory + 事后 reflection 注入 prompt | 有 outcome memory，按 exit date 做 cutoff | 已补齐基本 contract；reflection 仍较轻 |
| Point-in-time 数据 | 有 market_data_validator | `BacktestFetcher` 有价格截断、SEC filing-date gate、SEC/FRED evidence replay；历史 mode 对未版本化 sector/industry fail-closed | 基础更好，provider news/universe 仍待外部证据 |
| Backtest 指标 | 无 training-cutoff 处理 | hit rate / Sharpe / info coefficient / training-cutoff split (`backtest/scorer.py`) | 本仓库明显更严谨 |
| Checkpoint/断点续跑 | LangGraph state persistence | 主 pipeline 通过 durable stage artifacts resume；backtest 也支持缓存 resume | 当前 contract 已覆盖 |

---

## 2. Historical correctness issues and current status

### 2.1 Macro 数据是静态硬编码文本，且已过期 — fixed

`agents/macro.py:16-43` 的 `MACRO_CONTEXT` 写死 "as of April 2026" 的 Fed/BNM/FX 数据，代码注释自己也承认（`macro.py:15`: "Initial hardcoded macro context — will be replaced with live API data later"）。当前日期 2026-08-12，Macro/FX agent 每次分析都在用过期数据参与投票，且没有 `as_of` / `source` / `freshness` 字段，agent 无法知道自己在用旧数据。

**当前状态**：已移除硬编码上下文，改为带 `as_of_date` / `available_as_of` / `source` 的 `MacroSnapshot`。无可用 snapshot 时 agent fail closed 为 neutral/low；replay 也复用同一 availability predicate。

### 2.2 Technical 指标有两套互相矛盾的实现 — fixed

- `agents/technical.py:37-61` 的 `compute_macd()` 用简单移动平均（SMA）近似 MACD。
- `data/technicals.py:41-47` 用真正的 EMA（`close.ewm(span=12/26/9)`）计算 MACD，这是标准定义。
- `synthesis/risk_checker.py:136` (`plan_action`) 调用的是后者 (`compute_technicals`)。

结果是 **TechnicalAgent 看到的 MACD 信号和 RiskChecker 用来定 entry/stop/target 的 MACD 是两个不同的数字**，两者可能方向相反。TradingAgents 专门做了 verified snapshot 正是为了避免这种"LLM 层和执行层各算一套"的错位。

**当前状态**：analyst payload 和 RiskChecker 都消费 `data/technicals.py::compute_technicals()`；运行时还会把 RSI canonicalize，并丢弃超出观察到的 OHLC 范围的 support/resistance。technical prompt 的 observed highs/lows 也来自 bar high/low，而非 close。

### 2.3 Synthesizer 被 prompt 强制不能输出 neutral — fixed

`synthesis/synthesizer.py:131`: `"Never default to 'neutral' — take a position while acknowledging uncertainty."`

这与实际数据矛盾：`RiskChecker.plan_action()` 在 `_MIN_CONVICTION_FOR_LEVELS=0.3` / `_MIN_CONVERGENCE_FOR_LEVELS=0.4` 以下会返回"too mixed, wait"（`risk_checker.py:124-134`）——也就是说**系统内部已经有一层在纠正 forced-direction 造成的假信号**，说明这个约束本身是错的，只是被下游悄悄兜住了。

**当前状态**：prompt 明确允许 neutral；deterministic actionability gate 会把弱/矛盾方向降为 neutral。public briefing 仍只表达研究判断，不承担 private portfolio decision。

### 2.4 `signal_convergence` 由 LLM 自报，无范围校验 — fixed

`models/synthesis.py:10-13` 的 `ConvictionScore` 没有 `field_validator` 约束 `score ∈ [-1,1]` 或 `signal_convergence ∈ [0,1]`。这个数字完全由 Synthesizer 的 LLM 输出自行填写（`synthesizer.py:72-79` 的 schema 只声明了 description，没有 range 约束），而它又是 `RiskChecker` 决定是否给出精确 entry/stop/target 的核心开关（`risk_checker.py:12-13`）。一个数字既不可信也没有校验，却驱动了下游是否"敢下单"的判断。

**当前状态**：`signal_convergence` 与 directional consensus 均由 typed analyst reports、confidence 和 available-evidence denominator deterministic 计算；LLM 返回的数值被忽略。

### 2.5 Risk 数字本身有误导性表述和缺失维度 — fixed

`synthesis/risk_checker.py:69-90` 的 `_estimate_max_drawdown()`：
- 遍历的是 **整个 `price_history`**（本仓库 AAPL 历史数据是 2016–2026，10 年），但输出文案硬写 `"Historical max drawdown: ... over past year"`（`risk_checker.py:88`）—— 文案与实际计算窗口不符。
- `risk_reward = conviction_abs / volatility`（`risk_checker.py:29-32`）是"conviction 除以年化波动率"，跟真实的 entry→stop / entry→target 距离比完全无关，命名成 `risk_reward_ratio` 会误导使用者。
- 旧版曾在 research briefing 中混入 position-size 文案，**不读取真实持仓也不应承担组合层 cap**。

**当前状态**：drawdown 文案与可用历史窗口一致，risk/reward 基于真实 entry/stop/target 距离计算；RiskChecker 不读取 private holdings，也不计算 portfolio caps。

### 2.6 Backtest 的历史 briefing 日期字段是"今天"，不是 as_of_date — fixed

`synthesis/synthesizer.py:173`: `date=date.today().isoformat()`。这意味着 backtest 跑历史某一天的 briefing，`Briefing.date` 字段永远显示运行时的日期，不是被分析的历史日期——任何依赖 `briefing.date` 做时间轴回溯的逻辑都会读到错的日期。

**当前状态**：briefing 保存 `date` 与 `data_as_of`，分别表达运行日和实际读取到的最新 price bar；历史测试覆盖了该 contract。

### 2.7 Backtest settings 漏了 synthesis_model，training-cutoff 判断不完整 — fixed

`backtest/runner.py:111-118` 保存 settings 时只写了 `quick_think_model` / `deep_think_model`，**没有 `synthesis_model`**。但 `backtest/scorer.py:211` 的 `_effective_cutoff()` 会去读 `synthesis_model` 这个 key 来算 training-cutoff（`MODEL_TRAINING_CUTOFFS` 里 sonnet 的 cutoff 是全局里最晚的一个，`scorer.py:30`）。缺了这个 key，post-cutoff 的"干净样本"判断实际上漏了 synthesis 模型可能带来的污染窗口。

**当前状态**：runner 与 scorer 的 training-cutoff settings 已包含 synthesis model；session mode 明确标为 `in-session`，不伪装成 provider run。

### 2.8 Point-in-time metadata — fail-closed

`backtest/fetcher.py` 的 `_build_info()` 不再把当前 provider 的 sector/industry
复制进 historical packet；没有版本化 metadata 时这两个字段为空。market cap、P/E、
forward estimates、beta 等可能泄漏的字段也继续置空。若未来需要 sector-aware
macro reasoning，必须提供带 as-of/availability 的 metadata replay，而不是恢复当前
provider lookup。

---

## 3. Documentation drift resolved / remaining

- The storage layout and Malaysia fetcher descriptions have been aligned in the current README/CLAUDE documentation.
- The repository now has runnable pytest, ruff, and web typecheck gates. Current verification is recorded in the durable OOS report.
- Remaining documentation work is to keep this historical comparison updated when the public research boundary changes; private portfolio gates remain out of scope.

---

## 4. 值得抄的 TradingAgents 设计：Outcome Memory

这是本仓库和 TradingAgents 差距最大的一块，也是性价比最高的补强点。TradingAgents 的 [memory.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/agents/utils/memory.py) + [reflection.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/reflection.py) 做的事：交易结束后回填 realized return，生成一段反思文字，注入到下一次同 ticker / 同类情境的分析 prompt 里。

本仓库已有对应的 outcome backend（`BacktestTrial.realized_return` 可记录为 resolved outcome），并由 `orchestrator.py` 按 `before=self.as_of_date` 注入 synthesis。读取 cutoff 是硬 contract，避免 backtest 看到尚未到期的结果。

---

## 5. 建议的新 flow

```
L0  Point-in-time Snapshot + Data QA
        ↓
L1  Deterministic Screener（便宜地筛选整个 watchlist）
        ↓
L2  Specialist Analysts（只对 shortlist / 已持仓 / 有重大事件的 ticker 跑深度分析）
        ↓
L3  Research Manager / Debate Judge（在 bull/bear debate 之上加一层裁决：thesis / 反例 / invalidation）
        ↓
L4  Trader Proposal（entry / stop / target / horizon / catalyst —— 沿用现有 deterministic RiskChecker 思路）
        ↓
Outcome Memory context（到期回填 realized return，形成下次分析的记忆）
```

L0/L4 已有对应实现（`BacktestFetcher`、replay evidence gates、`RiskChecker.plan_action`）；研究裁决与 outcome memory 已接入。下游 debate/research/synthesis 共享完整 typed reports 与 provenance envelope，组合层 gate 不在本仓库范围内。L1 screener/deep-dive 分层和逐 claim evidence citations 仍是可选的后续架构工作。

---

## 6. 执行顺序

**P0 — correctness**

Completed: dated macro snapshot, unified technical indicators, neutral/actionability gate,
deterministic convergence, historical briefing provenance, synthesis training cutoff,
RiskChecker wording/ratio, OHLC hygiene, and evidence-aware historical replay.

**P1 — remaining quality work**

1. Add a provider-versioned historical news feed (the current SEC event replay is
   only a primary event layer), then run a real paired provider backtest. The
   `external-validate` gate now blocks this until the provider run is authenticated
   and paired to the exact packet manifest.
2. Add evidence/source/as-of references at the individual claim level if downstream
   consumers need citation-grade prose; the current envelope covers stage-level provenance.
3. Split a cheap deterministic screener from the expensive deep-dive path only when a
   fixed universe and selection protocol are frozen before a holdout.
4. Keep `RiskChecker` and portfolio ownership separate; benchmark alpha and sizing remain
   in the private consumer.

**P2 — optional infrastructure**

1. Add explicit model cost/latency fields to the run manifest if operational
   budgeting becomes important; durable stage resume already exists.
2. Add a second provider seam only if a second LLM provider is actually required.

The current backtest is mechanically reproducible enough for engineering validation,
but it is not evidence of durable alpha: SEC events are not a complete provider
news feed, the fixed universe has survivorship bias, execution costs are not
externally calibrated, and the no-API-key session path does not validate production
model-provider behavior. Run `--mode external-validate` before treating a future
provider score as an external result. See the durable OOS report for the latest
strict long-hold comparison and promotion-gate verdict.
