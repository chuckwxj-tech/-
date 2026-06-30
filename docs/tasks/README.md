# 任务卡片（TASK）

Claude 在此产出任务，Codex 按卡片执行。一个 TASK = 一个分支 = 一个 PR。

- 新任务从 `TASK-TEMPLATE.md` 复制。
- 命名：`TASK-XXXX-<slug>.md`。
- 状态在卡片顶部标注：TODO / IN-PROGRESS(codex) / IN-REVIEW(claude) / DONE。

## 第一批任务顺序（先建地基，别先写策略）

> 现状：项目已有数据层、动量因子、最小回测引擎、P0 指标、宽池回测。下表是把现有结构对齐到 PRD 的推荐路线，按需取用。

| 编号 | 标题 | 说明 |
|---|---|---|
| TASK-0001 | 项目骨架 + CI | pyproject / ruff / pytest / CI（**已基本就位**，CI 见 `.github/workflows/ci.yml`） |
| TASK-0002 | ETF universe 管理 | 分类、成交额/规模过滤、point-in-time 宇宙（治幸存者偏差） |
| TASK-0003 | DataHub 数据源中台 | 统一入口、缓存元数据校验（对齐 ADR-0001） |
| TASK-0004 | 数据质量检查 | 停牌/缺失/上市差异显式报告 |
| TASK-0005 | 动量因子计算 | 已有，补 IC/ICIR/分组单调性诊断 |
| TASK-0006 | 风控模块 | 单标的上限、同主题上限、回撤/趋势防守、现金/防守仓 |
| TASK-0007 | 回测引擎 | 已有最小版，补完整风控钩子（对齐 ADR-0002） |
| TASK-0008 | 手动调仓报告 | 输出可执行的人工下单清单 |
| TASK-0009 | 每周 signal 生成 | `scripts/make_weekly_signal.py` 类入口 |
| TASK-0010 | 策略对比报告 | 多实验横向对比（对齐 `docs/EXPERIMENTS_TODO.md`） |

待办指标/实验清单见：`docs/METRICS_TODO.md`、`docs/EXPERIMENTS_TODO.md`。
