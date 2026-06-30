# 任务清单：补齐回测业绩指标（Metrics）

## 背景

当前 `src/aetf_momentum/research/pipeline.py` 的 `_build_summary()` 只输出 7 个字段：
`factor / start / end / initial_cash / final_equity / total_return / trades`。

只有一个「总收益」，没有任何**风险**和**风险调整后收益**指标，无法判断策略好坏与稳健性。
本任务要在不改动回测引擎逻辑的前提下，新增一套标准业绩指标，并写进 `summary.json` 和 `report.html`。

数据来源：`BacktestResult` 已提供 `equity`（含 `date / total_equity / turnover` 列）、`trades`、`positions`。
约定：无风险利率默认 0；年化系数用 252 个交易日。

---

## 一、收益类指标（Return）

- [ ] **CAGR（年化复合收益率）**：`(final/initial)**(252/天数) - 1`
- [ ] **年化收益率（algebraic）**：日收益均值 × 252（与 CAGR 并列给出）
- [ ] **累计收益曲线归一化**：在 equity 基础上加一列 `cum_return = total_equity/initial - 1`

## 二、风险类指标（Risk）

- [ ] **年化波动率**：日收益标准差 × √252
- [ ] **最大回撤（Max Drawdown）**：净值曲线峰值到谷底的最大跌幅
- [ ] **最大回撤区间**：回撤起始日期、谷底日期、（如有）修复日期
- [ ] **回撤持续天数**：最长水下（underwater）天数
- [ ] **下行波动率（Downside Deviation）**：只统计负收益的标准差，给 Sortino 用

## 三、风险调整收益（Risk-adjusted）

- [ ] **Sharpe 比率**：`(年化收益 - rf) / 年化波动率`
- [ ] **Sortino 比率**：`(年化收益 - rf) / 下行波动率`
- [ ] **Calmar 比率**：`CAGR / |最大回撤|`

## 四、交易行为类指标（Trading）

- [ ] **年化换手率（Turnover）**：用 equity 里的 `turnover` 列求均值后年化
- [ ] **胜率（Win Rate）**：盈利交易笔数 / 总交易笔数（注意按「平仓」配对，或先用日收益为正的占比近似）
- [ ] **盈亏比（Profit Factor）**：总盈利 / 总亏损（绝对值）
- [ ] **平均每笔成本**：`trades` 里 `fee + slippage` 合计 / 笔数
- [ ] **总交易成本占比**：累计成本 / 初始资金

## 五、动量信号有效性指标（Momentum-specific，进阶可选）

> 这部分针对「动量测量」本身是否有效，而非只看回测净值。

- [ ] **IC（Information Coefficient）**：每个调仓日的动量得分 vs 下一期收益的横截面相关系数（Spearman），输出均值与 ICIR（IC均值/IC标准差）
- [ ] **分组单调性**：按动量得分分 N 组，看高分组收益是否单调高于低分组
- [ ] **多空价差**：Top 组收益 - Bottom 组收益

---

## 六、工程落地要求

- [ ] 新建 `src/aetf_momentum/research/metrics.py`，所有指标做成**纯函数**（输入 DataFrame，输出 dict），不依赖引擎内部状态，便于单测
- [ ] 在 `_build_summary()` 中调用 metrics，把上述指标合并进 `summary.json`
- [ ] 升级 `_build_html_report()`：除指标表外，加 **净值曲线** 和 **回撤曲线** 两张 plotly 图（项目依赖已含 plotly）
- [ ] 边界处理：天数<2、波动率为 0、最大回撤为 0、无交易等情况返回 `NaN`/`0` 而不报错
- [ ] **测试先行**（遵守 AGENTS.md）：在 `tests/` 下用构造的已知 equity 序列验证每个指标数值正确（例如给定固定净值序列，手算 Sharpe/MaxDD 后断言）
- [ ] 收尾运行：`python -m pytest` / `python -m ruff check .` / `python -m aetf_momentum.app.cli --help` 三条全绿

## 优先级建议

1. **P0（先做）**：CAGR、年化波动率、最大回撤、Sharpe、Calmar、换手率 + report.html 两张图
2. **P1**：Sortino、下行波动率、胜率、盈亏比、交易成本统计
3. **P2（进阶）**：IC / ICIR、分组单调性、多空价差
