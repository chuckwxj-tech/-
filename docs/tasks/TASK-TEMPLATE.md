# TASK-XXXX: <标题>

> 一个 TASK = 一个分支（`task/TASK-XXXX-<slug>`）= 一个 PR。Codex 只做本任务，不扩大范围。

## 背景
<为什么需要这个任务>

## 目标
<要实现什么，落在哪个模块/文件>

## 输入
<参数 / 配置 / 数据>

## 输出
<产物：函数/文件/报告，给出结构或 schema>

## 验收标准
- [ ] <可执行、可验证的判定条件>
- [ ] `pytest` 通过（新增逻辑必须有测试）
- [ ] `ruff check .` 通过
- [ ] smoke：`python -m aetf_momentum.app.cli backtest run --factor-preset daily_momentum --panel examples/sample_panel.csv --output artifacts/smoke` 成功

## 风险点
<未来函数 / 数据泄露 / 风控绕过 / 成本假设 等需特别检查的点>

## Codex 执行提示
<明确边界：只做什么、不要做什么>
