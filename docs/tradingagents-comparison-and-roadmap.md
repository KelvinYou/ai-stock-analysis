# TradingAgents 对比 + 修复路线图

日期: 2026-08-12
参考: [TradingAgents README](https://github.com/TauricResearch/TradingAgents/blob/main/README.md) · [graph/setup.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/setup.py) · [dataflows/market_data_validator.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/dataflows/market_data_validator.py) · [agents/utils/memory.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/agents/utils/memory.py) · [graph/reflection.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/reflection.py)

## 结论

**不整体迁移到 TradingAgents。** 本仓库的 deterministic 基础（typed backtest scorer、point-in-time fetcher、独立 RiskChecker）已经比 TradingAgents 文档描述的更严谨。但当前 pipeline 存在几个**实际会影响信号质量的 bug**，且缺一层"研究裁决 → 交易计划 → portfolio gate → outcome memory"的分层。以下所有代码问题均已逐条对照源码核实（非转述猜测）。

---

## 1. 两边架构对比

| 维度 | TradingAgents | 本仓库 | 结论 |
|---|---|---|---|
| Analyst 团队 | 4 个，图内顺序执行 | 4 个，`asyncio.gather` 并行 (`orchestrator.py:64`) | 本仓库更快更省钱 |
| Debate | Bull/Bear，多轮 | Bull/Bear，多轮 (`debate/engine.py`) | 打平 |
| 研究裁决 | 有 Research Manager 汇总 debate | **没有**，debate 直接喂给 Synthesizer | TradingAgents 多一层 |
| 交易执行层 | 独立 Trader agent 生成 entry/stop/target | `RiskChecker.plan_action()` deterministic 生成 (`risk_checker.py:114`) | 本仓库更可靠（非 LLM 捏造数字） |
| Portfolio Gate | Portfolio Manager 读真实持仓，approve/reject | `RiskChecker` 只看单票 beta/sector，**不读真实持仓** | TradingAgents 更完整 |
| 跨次记忆/reflection | 持久化 decision memory + 事后 reflection 注入 prompt | **没有** — 每次 run 都是冷启动 | TradingAgents 明显更强，值得抄 |
| Point-in-time 数据 | 有 market_data_validator | `BacktestFetcher` 已实现 truncation + financial lag (`backtest/fetcher.py:19`)，但 sector/shares outstanding 仍用当前值 | 本仓库基础更好，细节有漏洞 |
| Backtest 指标 | 无 training-cutoff 处理 | hit rate / Sharpe / info coefficient / training-cutoff split (`backtest/scorer.py`) | 本仓库明显更严谨 |
| Checkpoint/断点续跑 | LangGraph state persistence | 无（backtest 有基于文件的 resume，pipeline 本身没有） | TradingAgents 更抗故障，但当前规模优先级低 |

---

## 2. 已验证的 correctness 问题（P0）

### 2.1 Macro 数据是静态硬编码文本，且已过期

`agents/macro.py:16-43` 的 `MACRO_CONTEXT` 写死 "as of April 2026" 的 Fed/BNM/FX 数据，代码注释自己也承认（`macro.py:15`: "Initial hardcoded macro context — will be replaced with live API data later"）。当前日期 2026-08-12，Macro/FX agent 每次分析都在用过期数据参与投票，且没有 `as_of` / `source` / `freshness` 字段，agent 无法知道自己在用旧数据。

**修复**：把 `MACRO_CONTEXT` 换成结构化 snapshot（`value` / `as_of` / `source` / `freshness`），拿不到实时数据时返回 `unknown` + 降低该 agent 的 confidence，而不是 fallback 到旧文本。

### 2.2 Technical 指标有两套互相矛盾的实现

- `agents/technical.py:37-61` 的 `compute_macd()` 用简单移动平均（SMA）近似 MACD。
- `data/technicals.py:41-47` 用真正的 EMA（`close.ewm(span=12/26/9)`）计算 MACD，这是标准定义。
- `synthesis/risk_checker.py:136` (`plan_action`) 调用的是后者 (`compute_technicals`)。

结果是 **TechnicalAgent 看到的 MACD 信号和 RiskChecker 用来定 entry/stop/target 的 MACD 是两个不同的数字**，两者可能方向相反。TradingAgents 专门做了 verified snapshot 正是为了避免这种"LLM 层和执行层各算一套"的错位。

**修复**：删除 `agents/technical.py` 里的 `compute_rsi/compute_macd`，analyst 工具和 RiskChecker 统一消费 `data/technicals.py::compute_technicals()` 产出的同一份 `TechnicalSnapshot`。

### 2.3 Synthesizer 被 prompt 强制不能输出 neutral

`synthesis/synthesizer.py:131`: `"Never default to 'neutral' — take a position while acknowledging uncertainty."`

这与实际数据矛盾：`RiskChecker.plan_action()` 在 `_MIN_CONVICTION_FOR_LEVELS=0.3` / `_MIN_CONVERGENCE_FOR_LEVELS=0.4` 以下会返回"too mixed, wait"（`risk_checker.py:124-134`）——也就是说**系统内部已经有一层在纠正 forced-direction 造成的假信号**，说明这个约束本身是错的，只是被下游悄悄兜住了。

**修复**：拆成两个字段 `research_view: buy/neutral/sell`（LLM 的诚实判断）和 `trade_decision: approve/watch/reject`（是否要据此行动）。neutral/watch 是正确结果，不是失败。

### 2.4 `signal_convergence` 由 LLM 自报，无范围校验

`models/synthesis.py:10-13` 的 `ConvictionScore` 没有 `field_validator` 约束 `score ∈ [-1,1]` 或 `signal_convergence ∈ [0,1]`。这个数字完全由 Synthesizer 的 LLM 输出自行填写（`synthesizer.py:72-79` 的 schema 只声明了 description，没有 range 约束），而它又是 `RiskChecker` 决定是否给出精确 entry/stop/target 的核心开关（`risk_checker.py:12-13`）。一个数字既不可信也没有校验，却驱动了下游是否"敢下单"的判断。

**修复**：`signal_convergence` 改成 deterministic 计算 —— 4 个 analyst 方向一致度 + confidence 加权 + 是否有高质量反例 + 数据新鲜度 penalty + 缺失数据 penalty。LLM 只负责写 `explanation`，不负责产出这个数字。

### 2.5 Risk 数字本身有误导性表述和缺失维度

`synthesis/risk_checker.py:69-90` 的 `_estimate_max_drawdown()`：
- 遍历的是 **整个 `price_history`**（本仓库 AAPL 历史数据是 2016–2026，10 年），但输出文案硬写 `"Historical max drawdown: ... over past year"`（`risk_checker.py:88`）—— 文案与实际计算窗口不符。
- `risk_reward = conviction_abs / volatility`（`risk_checker.py:29-32`）是"conviction 除以年化波动率"，跟真实的 entry→stop / entry→target 距离比完全无关，命名成 `risk_reward_ratio` 会误导使用者。
- `_suggest_position_size()`（`risk_checker.py:56-67`）只用 conviction/convergence/volatility 三个数字算仓位百分比，**不读取真实持仓、不做 stop distance 反推仓位、没有 sector/ticker exposure cap**。

**修复**：改成 `portfolio risk budget → stop distance → position size → sector/ticker exposure cap → approve/watch/reject` 的链路，并读取 `personal-os` 里 `data/finance/portfolio` 的真实持仓做 exposure 检查（这一步正好能把这个工具和 `wealth-manager` skill 打通）。

### 2.6 Backtest 的历史 briefing 日期字段是"今天"，不是 as_of_date

`synthesis/synthesizer.py:173`: `date=date.today().isoformat()`。这意味着 backtest 跑历史某一天的 briefing，`Briefing.date` 字段永远显示运行时的日期，不是被分析的历史日期——任何依赖 `briefing.date` 做时间轴回溯的逻辑都会读到错的日期。

**修复**：`AnalysisPipeline` 已经有 `as_of_date` 参数（`orchestrator.py:34`），传给 `synthesizer.synthesize()` 并用它写 `Briefing.date`，而不是 `date.today()`。

### 2.7 Backtest settings 漏了 synthesis_model，training-cutoff 判断不完整

`backtest/runner.py:111-118` 保存 settings 时只写了 `quick_think_model` / `deep_think_model`，**没有 `synthesis_model`**。但 `backtest/scorer.py:211` 的 `_effective_cutoff()` 会去读 `synthesis_model` 这个 key 来算 training-cutoff（`MODEL_TRAINING_CUTOFFS` 里 sonnet 的 cutoff 是全局里最晚的一个，`scorer.py:30`）。缺了这个 key，post-cutoff 的"干净样本"判断实际上漏了 synthesis 模型可能带来的污染窗口。

**修复**：`runner.py` 的 settings dict 补上 `"synthesis_model": self.settings.synthesis_model`。

### 2.8 Point-in-time 还有两个小漏洞（优先级低于以上）

`backtest/fetcher.py:174-177` 的 `_build_info()` 用的是 `stock.info`（当前实时数据）取 sector/industry/sharesOutstanding，不是历史某天的值。sector 变化频率低、shares outstanding 变化也慢，实际影响小于上面几条，但如果要做严谨的策略有效性验证，这是需要标注的已知偏差，不是"零缺陷的 point-in-time"。

---

## 3. 文档 drift（不影响信号质量，但会让下一个读代码的人/agent 读错文件）

- `CLAUDE.md:37` 和 `README.md:231` 都描述 `data/<TICKER>/<DATE>/market_data.json` 是唯一存储格式；实际 `DataStore`（`data/store.py:21-31` 注释里写得很清楚）主用的是**扁平布局** `data/AAPL/{price_history.csv, fundamentals.json, analyst_reports.json, debate_result.json, briefing.json}`，dated 子目录只是 backtest 的 legacy fallback。已用 `find data/AAPL` 核实磁盘上确实是扁平布局，没有 `market_data.json` 这个文件名。
- `README.md:97,176` 把 Malaysia/Bursa fetcher 标成"stub"，但 `data/my_market.py` 已经是 193 行的完整实现（含 `BURSA_ALIASES` 映射表、`.KL` 后缀解析、真实 yfinance 调用），不再是占位代码。
- 仓库没有 `tests/` 目录，`.venv/bin` 里没有 `pytest`/`ruff`，`web/node_modules/.bin` 里没有 `tsc` —— 也就是说 README 里写的 `pytest` / `ruff check` / 类型检查命令**当前环境跑不了**，quality gate 目前是空的。

---

## 4. 值得抄的 TradingAgents 设计：Outcome Memory

这是本仓库和 TradingAgents 差距最大的一块，也是性价比最高的补强点。TradingAgents 的 [memory.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/agents/utils/memory.py) + [reflection.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/reflection.py) 做的事：交易结束后回填 realized return，生成一段反思文字，注入到下一次同 ticker / 同类情境的分析 prompt 里。

本仓库已经有对应的原始数据（`backtest/scorer.py` 算出的 hit rate / info coefficient，`BacktestTrial.realized_return`），**只是没有接回主 pipeline**。这是 §5 路线图里优先级最高的一项。

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
L5  Portfolio Risk Gate（读真实持仓，输出 APPROVE / WATCH / REDUCE / REJECT）
        ↓
L6  Outcome Log + Calibration（到期回填 realized return，形成下次分析的记忆）
```

L0/L1/L4 本仓库已经有对应实现的骨架（`BacktestFetcher`、screener 页面、`RiskChecker.plan_action`），主要缺 L3（Research Manager）、L5 的组合层 gate、L6 的记忆回灌。

---

## 6. 执行顺序

**P0 — 先修正确性（不改架构，纯 bug fix）**
1. 移除 `macro.py` 里的硬编码 `MACRO_CONTEXT`，换成带 `as_of`/`source`/`freshness` 的结构化 snapshot。
2. 删掉 `agents/technical.py` 里那套近似 MACD，统一用 `data/technicals.py::compute_technicals()`。
3. 去掉 synthesizer 里 "Never default to neutral"，拆成 `research_view` / `trade_decision` 两个字段。
4. `signal_convergence` 改成 deterministic 计算，不再由 LLM 自报。
5. 修 `Briefing.date`（用 `as_of_date` 而非 `date.today()`）、backtest settings 补 `synthesis_model`、`_estimate_max_drawdown` 的文案改成"整段历史"或真的裁成一年、`risk_reward_ratio` 改成基于真实 entry/stop/target 距离计算。

**P1 — 补分层**
1. 加 Research Manager → Trader → Portfolio Gate 三个模块。
2. 拆分 screener mode（便宜、跑全 watchlist）和 deep-dive mode（贵、只跑 shortlist）。
3. 给每条 analyst claim 标 evidence/source/as-of。
4. `RiskChecker` 接入 `personal-os` 里的真实持仓（`data/finance/portfolio`）做组合层 exposure/相关性检查，并算 benchmark alpha。

**P2 — 基建打磨**
1. 加 run manifest、cost/latency tracking、pipeline 断点续跑（backtest 已有基于文件的 resume，可以扩展到主 pipeline）。
2. 只有真的要接第二个 LLM provider 时才抽象 provider seam，现在不需要。
3. 补 `tests/` 目录 + CI 里跑得动的 `pytest`/`ruff`/`tsc`，同步修一遍 `CLAUDE.md`/`README.md` 的文档 drift（扁平布局、MY fetcher 已不是 stub）。

在 P0 修完之前，任何 backtest 结果都只能当 engineering smoke test，不能当策略有效性的证据 —— 因为 `Briefing.date` 错误和 macro 数据过期这两条已经足够污染回测的可信度。
