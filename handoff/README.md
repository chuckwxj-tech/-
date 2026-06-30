# handoff —— 结构化交接（可选）

主交接物是 **PR**。本目录用于需要结构化上下文时的补充交接，不替代 PR。

- `claude_to_codex/`：Claude 给 Codex 的任务上下文（如 `TASK-0001.json`），点名要读的文件、边界、验收标准。
- `codex_to_claude/`：Codex 执行后的结果摘要（如 `TASK-0001-result.md`），含改了什么、测试结果、风险、后续。

规则：
- 不在此存放数据、密钥、token、券商配置。
- 交接文件随对应 PR 一起提交，便于回溯。
