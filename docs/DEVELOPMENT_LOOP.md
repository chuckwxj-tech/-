# A-share ETF Momentum Development Loop

## Goal

Build a reproducible A-share ETF momentum rotation research framework. The first version focuses on local research backtests, not live trading.

## Architecture

The framework follows a thin pipeline:

`config -> data provider/cache -> schema validation -> strategy -> backtest -> recorder/report`

Loop 1 builds only the project skeleton and data layer. Later loops add signals, backtesting, reporting, parameter scans, walk-forward analysis, CLI workflows, and Streamlit UI.

## Loop Discipline

Each loop must deliver one verifiable vertical slice.

At the start of each loop:

1. Read `README.md`.
2. Read `progress.md` if it exists.
3. Read the current tests.

At the end of each loop, run:

```powershell
python -m pytest
python -m ruff check .
python -m aetf_momentum.app.cli --help
```

If a command fails, fix the failure before starting another loop.

## Loop 1: Data Layer MVP

Acceptance criteria:

- Read ETF symbols from `configs/universe.yaml`.
- Pull daily ETF history through AKShare for a requested date range.
- Normalize fields to `date, symbol, open, high, low, close, volume, amount, adj_factor`.
- Skip dates before each ETF listing naturally by accepting sparse panels.
- Detect bad local data: empty frames, duplicate symbol/date rows, missing required prices, and missing expected sessions when a calendar is supplied.
- Cache raw symbol data and panel data as parquet.
- Support `refresh=True` to bypass cached files.
- Keep network access behind `AKShareProvider` so unit tests can use injected fake clients.
- Keep tests and ruff green.

## Future Loops

- Loop 2: momentum score, trend filters, rebalance dates, target weights, no-lookahead tests.
- Loop 3: pandas next-bar backtest engine with costs, slippage, cash, trades, equity, and positions.
- Loop 4: performance metrics and HTML report.
- Loop 5: parameter grid and robustness analysis.
- Loop 6: walk-forward out-of-sample workflow.
- Loop 7: Typer CLI commands and smoke tests.
- Loop 8: Streamlit UI that calls core modules only.
