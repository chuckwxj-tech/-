# Agent Constraints

This repository implements an A-share ETF momentum research framework. Agents must follow these constraints before changing code.

## Working Rules

- State assumptions before implementation when requirements are ambiguous.
- Prefer the minimum code that satisfies the current loop. Do not add speculative features.
- Touch only files required by the active loop. Do not refactor unrelated code.
- Use test-first development for behavior changes: write a failing test, verify the failure, then implement the smallest passing code.
- Keep all business logic under `src/aetf_momentum/`.
- Do not put notebooks or one-off scripts at the center of the system.
- At the end of each loop, run:
  - `python -m pytest`
  - `python -m ruff check .`
  - `python -m aetf_momentum.app.cli --help`
- If verification fails, fix the failure before continuing.

## Project Direction

- Build a lightweight research framework: AKShare data layer plus a pandas backtest engine, with vectorbt only as an optional acceleration path.
- Do not copy third-party framework code. Borrow architecture ideas only.
- First-stage scope is research and backtesting. Do not implement live trading.
- All strategy signals must use next-bar execution. Never trade on the same close that generated the signal.
- Persist reproducibility metadata for later loops: config, parameters, date range, package version, and run time under `artifacts/records`.

## Technical Constraints

- Python 3.11+
- Core libraries: pandas, numpy, scipy, plotly, typer, pydantic, pyarrow, pytest, ruff
- Data source priority: AKShare
- First AKShare interfaces:
  - `fund_etf_hist_em`
  - `fund_etf_spot_em`
- Required data schema:
  - `date`
  - `symbol`
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
  - `amount`
  - `adj_factor` optional

## Loop 1 Acceptance Criteria

- Initialize project metadata, pytest, and ruff.
- Implement ETF OHLCV schema normalization and validation.
- Implement `AKShareProvider`:
  - `get_etf_spot()`
  - `get_etf_history(symbol, start, end, adjust)`
  - `get_panel(symbols, start, end, adjust)`
- Implement parquet cache:
  - `cache/raw/{symbol}.parquet`
  - `cache/panel/etf_panel_{hash}.parquet`
  - `refresh=True` bypasses existing cache.
- Tests must cover schema validation, empty data, duplicate dates, missing prices, missing sessions, symbol normalization, and cache hits.
- Write `progress.md` with completed work, unfinished work, known risks, and the next loop recommendation.
