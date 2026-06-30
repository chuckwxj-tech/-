# AETF Momentum

A lightweight A-share ETF momentum rotation research framework.

The first implementation loop builds the data layer: schema normalization, AKShare access, parquet caching, and smoke-testable CLI wiring.

## Development

```powershell
$env:PYTHONPATH = ""
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m aetf_momentum.app.cli --help
```

## Smoke Backtest

List selectable factor presets:

```powershell
$env:PYTHONPATH = ""
.\.venv\Scripts\python.exe -m aetf_momentum.app.cli factor list
```

Run the sample momentum factor against the local sample ETF panel:

```powershell
$env:PYTHONPATH = ""
.\.venv\Scripts\python.exe -m aetf_momentum.app.cli backtest run --factor-preset daily_momentum --panel examples/sample_panel.csv --output artifacts/smoke
```

Run a selected factor preset against AKShare data from `configs/universe.yaml`:

```powershell
$env:PYTHONPATH = ""
.\.venv\Scripts\python.exe -m aetf_momentum.app.cli backtest run --factor-preset risk_adjusted_momentum --universe configs/universe.yaml --start 2015-01-01 --output artifacts/latest
```

You can still run a custom YAML strategy:

```powershell
$env:PYTHONPATH = ""
.\.venv\Scripts\python.exe -m aetf_momentum.app.cli backtest run --strategy configs/strategy.yaml --universe configs/universe.yaml --start 2015-01-01 --output artifacts/latest
```

See `AGENTS.md` and `docs/DEVELOPMENT_LOOP.md` for the working constraints.
