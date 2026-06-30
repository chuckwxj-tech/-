# TASK-0011: 动量选股加「同类别持仓上限」

> 状态：TODO
> 分支：`task/TASK-0011-category-cap`　一个 TASK = 一个分支 = 一个 PR。
> 关联：`docs/EXPERIMENTS_TODO.md` P1「单类别持仓上限」。

## 背景

P0 实验（`docs/P0_TREND_CASH_EXPERIMENT_20260630.md`）证明：加回 MA120 趋势过滤 + 空仓切现金**没能降低回撤**（夏普 0.901、最大回撤仍 -38.72%）。
原因判断：回撤主因不是"该不该空仓"，而是**选中的持仓高度同质**——top3 经常整组扎在同一赛道（最新信号 3 个全是半导体；历史上常常全是银行）。同涨同跌，等于没分散。
因此从**源头分散**比在趋势过滤上打转更可能见效。

## 目标

在动量选股环节加入「同一类别最多选 N 只」的约束，让最终持仓跨类别分散。
落点：`src/aetf_momentum/strategy/momentum.py`（选股/目标权重构建），通过配置驱动，不硬编码。

## 输入

- `close`：现有的收盘价面板（symbol 为列）。
- **类别映射** `category_map: dict[symbol -> category]`：
  - 宽基/示例池来自 `configs/universe.yaml` 的 `bucket` 字段；
  - 宽池实验沿用现有 253 池的类别来源（见 `docs/results/broad_etf_200_biweekly_top3_20260630/selection_counts_by_etf.csv` 所用分类）。
  - 类别是**静态元数据**，与时间无关。
- 新增配置项 `max_per_category: int | None`（在 `MomentumConfig` / 策略 YAML 里），默认 `None` = 不限制（保持现有行为）。

## 输出

- `build_momentum_targets` 在按得分排序选 top_k 时，遵守"每个类别已选数量 < `max_per_category`"才纳入；类别满额则跳过该标的、顺延选下一个，直到凑满 top_k 或候选用尽。
- 一份实验报告 `docs/P1_CATEGORY_CAP_<日期>.md` + 结果到 `docs/results/p1_category_cap_<日期>/`（summary.json + equity.csv），对比三档：
  - 无上限（现状基线）
  - `max_per_category = 2`
  - `max_per_category = 1`
  并附**同区间基准**（有效池等权、剔黄金）对比 CAGR/波动/最大回撤/夏普/Calmar。

## 验收标准
- [ ] `max_per_category=None` 时结果与现状**完全一致**（回归不变，用测试锁定）。
- [ ] `max_per_category=1` 时，任一调仓日的持仓中同一类别标的数 ≤ 1（用构造数据的测试断言）。
- [ ] 类别满额时正确顺延到下一个高分、不同类别的标的；候选不足时持仓数可少于 top_k（剩余按既有规则处理，不得凭空补仓）。
- [ ] 报告给出三档 + 基准的横向指标表，并写一句结论：上限是否降低了最大回撤、夏普是否改善。
- [ ] `pytest` 通过（新逻辑必须有测试）。
- [ ] `ruff check .` 通过。
- [ ] smoke：`python -m aetf_momentum.app.cli backtest run --factor-preset daily_momentum --panel examples/sample_panel.csv --output artifacts/smoke` 成功。

## 风险点
- **未来函数**：类别映射是静态元数据，不得用任何含未来信息的分类（如按全样本表现归类）。仅用上市即确定的属性。
- **不得改成本/执行假设**：next-bar、费用、滑点保持 ADR-0002 不变。
- **向后兼容**：默认 `None`，现有 4 个 preset 与既有测试不能被破坏。
- 类别字段缺失的标的：归入 `"unknown"` 类别，不要静默丢弃，在报告里说明数量。

## Codex 执行提示
- 只动：`momentum.py`（选股逻辑 + 配置项）、必要的实验 runner、新增测试与实验报告。
- 不要：重构回测引擎、改 schema、改数据层、动其它 preset 的默认参数。
- 先写失败测试（max_per_category=1 的约束 + None 的回归一致性），再实现。
- 完成后在 `docs/EXPERIMENTS_TODO.md` 对应项打勾署名 `(codex)`，并在 PR 里按"策略 PR 合并门槛"逐条回答。
