# Progress

## Completed

- Created repository-level agent constraints in `AGENTS.md`.
- Created the development loop document in `docs/DEVELOPMENT_LOOP.md`.
- Initialized Python project metadata, dependencies, pytest, and ruff.
- Added default config files:
  - `configs/universe.yaml`
  - `configs/strategy.yaml`
  - `configs/costs.yaml`
- Implemented normalized ETF OHLCV schema utilities:
  - symbol normalization
  - AKShare column mapping
  - required-field validation
  - duplicate symbol/date detection
  - missing required value detection
- Implemented trading-session gap detection for supplied calendars.
- Implemented parquet cache for raw symbol data and panel data.
- Implemented `AKShareProvider` with:
  - `get_etf_spot()`
  - `get_etf_history(symbol, start, end, adjust, refresh=False)`
  - `get_panel(symbols, start, end, adjust, refresh=False)`
- Added Typer CLI wiring so `python -m aetf_momentum.app.cli --help` can smoke test the package.
- Added tests for schema validation, empty data, duplicate dates, missing prices, missing sessions, symbol normalization, cache round trip, cache key stability, provider caching, and panel caching.
- Implemented a first end-to-end factor backtest slice:
  - load universe symbols
  - update ETF panel cache
  - generate data quality HTML
  - build momentum factor target weights
  - execute next-bar pandas backtest
  - write equity, trades, positions, summary, and report artifacts
  - run `backtest run` from CLI with either a local panel or AKShare-backed universe
- Ran live AKShare smoke data update for `2024-01-01` to `2024-03-31`:
  - raw parquet cache for 8 configured ETFs
  - panel cache at `cache/panel/etf_panel_c3b2e470b0b12cd9.parquet`
  - data quality report at `artifacts/live_smoke/data_quality.html`
- Ran live AKShare-backed smoke backtest with `examples/momentum_smoke.yaml`:
  - summary at `artifacts/live_backtest/summary.json`
  - 83 trades
  - final equity `1179156.536243565`
  - total return `0.17915653624356498`
- Ran full-history AKShare data update for `2015-01-01` to `2026-06-30`:
  - panel cache at `cache/panel/etf_panel_f557b46d19355d1c.parquet`
  - data quality report at `artifacts/full_data/data_quality.html`
- Ran full-history formal strategy backtest with `configs/strategy.yaml`:
  - summary at `artifacts/full_backtest/summary.json`
  - 1499 trades
  - final equity `2594853.608955216`
  - total return `1.594853608955216`
  - minimum trade-log cash after costs: approximately zero (`1.736566446197685e-11`)
- Added factor preset selection:
  - `aetf factor list`
  - `aetf backtest run --factor-preset risk_adjusted_momentum ...`
  - available presets: `risk_adjusted_momentum`, `short_momentum`, `daily_momentum`, `long_momentum`
- Ran full-history selected-preset backtest with `risk_adjusted_momentum`:
  - summary at `artifacts/preset_full/summary.json`
  - 1499 trades
  - final equity `2594853.608955216`
  - total return `1.594853608955216`
- Added `docs/METRICS_TODO.md` from remote branch `claude/repo-overview-roadmap-i5ts8m`.
- Completed Metrics TODO P0:
  - CAGR
  - algebraic annualized return
  - cumulative return column in `equity.csv`
  - annualized volatility
  - max drawdown with peak/trough/recovery dates
  - max underwater days
  - Sharpe
  - Calmar
  - annualized turnover
  - Plotly equity curve and drawdown curve in `report.html`
- Completed Experiments TODO P0:
  - restored MA120 trend-filter comparison against the broad 253-ETF pool
  - changed momentum targets so missing top-k slots stay in cash instead of reallocating to surviving names
  - added optional `cash_annual_yield` support to the pandas backtest engine and pipeline
  - ran the no-filter vs MA120 + cash experiment for 2023-06-30 to 2026-06-30
  - wrote `docs/P0_TREND_CASH_EXPERIMENT_20260630.md` and `docs/results/p0_trend_cash_20260630/`

## Unfinished

- The current backtest engine is a minimal research engine. It supports next-bar open execution, cash, trades, positions, and simple costs, but not full risk controls.
- Metrics TODO P1/P2 remain: Sortino/downside deviation, win rate, profit factor, trading cost stats, IC/ICIR, grouped monotonicity, and long-short spread.
- Experiments TODO P1/P2 remain: top_k/top5/top8 comparison, same-category cap, lower max_weight, signal parameter comparisons, and IC diagnostics.
- Parameter scan, walk-forward, and Streamlit UI are future loops.

## Known Risks

- The local shell has `PYTHONPATH=D:\PythonLibs\Python313\site-packages`, which can override `.venv` packages. Verification commands in this workspace should clear `PYTHONPATH` first.
- Raw cache files are keyed only by symbol as requested. A later loop should add metadata checks before reusing cached data for a wider date range.
- Raw and artifact outputs are ignored by git. Re-run the commands in `README.md` if the local cache is removed.
- P0 trend filtering did not reduce the wide-pool strategy drawdown because it produced only two partial-cash rebalance signals in the 2023-06-30 to 2026-06-30 window.

## Next Loop Recommendation

Next, improve the research output quality:

1. Run Experiments TODO P1: top5/top8, same-category cap, and lower max_weight to address concentration risk.
2. Add Metrics TODO P1: Sortino, downside deviation, win rate, profit factor, and cost stats.
3. Add Metrics TODO P2: IC/ICIR, grouped monotonicity, and long-short spread.
4. Add parameter scan and walk-forward workflows.
