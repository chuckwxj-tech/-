# ADR-0001：数据源

- 状态：Accepted
- 日期：2026-06-30

## 背景

策略、风控、回测都需要统一、可缓存、可质检的 A 股 ETF 日线数据。

## 决策

- 主数据源：**AKShare**（`fund_etf_hist_em` / `fund_etf_spot_em`）。
- 网络访问全部封装在 `AKShareProvider` 后，便于单测注入假客户端。
- 标准 schema：`date, symbol, open, high, low, close, volume, amount, adj_factor(可选)`。
- 复权：默认 `qfq`（前复权）。
- 缓存：parquet，`cache/raw/{symbol}.parquet` 与 `cache/panel/etf_panel_{hash}.parquet`；`refresh=True` 绕过缓存。
- 已知补充源：宽池实验曾用 Futu OpenD QFQ 日线（有限频，需重试）。如长期采用，另写 ADR。

## 已知风险

- 当前为"当前在市 ETF"宇宙，存在**幸存者偏差**；point-in-time 宇宙是后续任务。
- raw 缓存仅按 symbol 命名，跨日期范围复用前应加元数据校验。
