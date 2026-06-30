# ADR-0000：协作模型 —— GitHub 当协议层

- 状态：Accepted
- 日期：2026-06-30

## 背景

项目由两个 AI 协作：Claude 与 Codex。直接让两个 agent "互相聊天"不可控、无记录、易跑偏。

## 决策

用 **GitHub 仓库作为协议层**，分工固定：

- **Claude = 大脑**：研究、架构、拆任务、写验收标准、审 PR。详见 `CLAUDE.md`。
- **Codex = 手**：按任务改代码、跑测试、开 PR、修 CI。详见 `AGENTS.md`。
- **GitHub = 真相**：Issue / PR / docs / 决策日志（本目录）是唯一状态来源。
- **人 = 最终合并 + 资金风险开关**：合并与"是否上真钱"只由人决定。

交接物：
- 任务卡片：`docs/tasks/TASK-xxxx-*.md`（或 GitHub Issue）。
- 代码交接：唯一通过 PR。一个 TASK = 一个分支 = 一个 PR。
- 可选结构化交接：`handoff/claude_to_codex/` 与 `handoff/codex_to_claude/`。
- 两个 agent **不共用同一工作目录、不同时改同一文件**。

## 落地原则（先简单，别上来搞全自动）

先跑通 **10 个 TASK + 10 个 PR + 10 次 CI**，系统即成型。暂不做全自动派单/合并。

## 后果

- 所有项目记忆可审计、可回溯。
- 防止"看起来赚钱、实则有未来函数/数据泄露"的回测被悄悄合并（见 `AGENTS.md` 的策略 PR 合并门槛）。
