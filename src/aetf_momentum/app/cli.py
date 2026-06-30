from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from aetf_momentum import __version__
from aetf_momentum.data.workflow import update_data_cache
from aetf_momentum.research.pipeline import run_factor_backtest
from aetf_momentum.strategy.presets import get_factor_preset_config, list_factor_presets

app = typer.Typer(help="AETF Momentum research CLI.")
data_app = typer.Typer(help="Data commands.")
backtest_app = typer.Typer(help="Backtest commands.")
factor_app = typer.Typer(help="Factor selection commands.")
app.add_typer(data_app, name="data")
app.add_typer(backtest_app, name="backtest")
app.add_typer(factor_app, name="factor")

DEFAULT_UNIVERSE_PATH = Path("configs/universe.yaml")
DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_ARTIFACTS_DIR = Path("artifacts")
DEFAULT_BACKTEST_OUTPUT = Path("artifacts/latest")


@app.callback()
def root() -> None:
    """Run AETF Momentum commands."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@factor_app.command("list")
def factor_list() -> None:
    """List factor presets that can be selected for ETF backtests."""
    for preset in list_factor_presets():
        typer.echo(f"{preset.name}: {preset.description}")


@data_app.command("update")
def data_update(
    config: Annotated[Path, typer.Option(help="Universe config path.")] = DEFAULT_UNIVERSE_PATH,
    start: Annotated[str, typer.Option(help="Start date.")] = "2015-01-01",
    end: Annotated[str | None, typer.Option(help="End date. Defaults to today.")] = None,
    adjust: Annotated[str, typer.Option(help="AKShare adjustment flag.")] = "qfq",
    cache_dir: Annotated[Path, typer.Option(help="Cache directory.")] = DEFAULT_CACHE_DIR,
    artifacts_dir: Annotated[
        Path, typer.Option(help="Artifacts directory.")
    ] = DEFAULT_ARTIFACTS_DIR,
    refresh: Annotated[bool, typer.Option(help="Bypass existing cached data.")] = False,
) -> None:
    """Fetch ETF data from the configured universe and write cache/artifacts."""
    result = update_data_cache(
        universe_path=config,
        start=start,
        end=end or date.today().isoformat(),
        adjust=adjust,
        cache_dir=cache_dir,
        artifacts_dir=artifacts_dir,
        refresh=refresh,
    )
    typer.echo(f"panel: {result.panel_path}")
    typer.echo(f"quality: {result.quality_report_path}")


@backtest_app.command("run")
def backtest_run(
    strategy: Annotated[Path | None, typer.Option(help="Strategy YAML path.")] = None,
    factor_preset: Annotated[
        str | None, typer.Option(help="Named factor preset to use when strategy is omitted.")
    ] = None,
    panel: Annotated[Path | None, typer.Option(help="CSV or parquet OHLCV panel path.")] = None,
    universe: Annotated[Path, typer.Option(help="Universe config path.")] = DEFAULT_UNIVERSE_PATH,
    start: Annotated[str, typer.Option(help="Start date when panel is omitted.")] = "2015-01-01",
    end: Annotated[
        str | None, typer.Option(help="End date when panel is omitted. Defaults to today.")
    ] = None,
    adjust: Annotated[
        str, typer.Option(help="AKShare adjustment flag when panel is omitted.")
    ] = "qfq",
    cache_dir: Annotated[
        Path, typer.Option(help="Cache directory when panel is omitted.")
    ] = DEFAULT_CACHE_DIR,
    output: Annotated[Path, typer.Option(help="Output directory.")] = DEFAULT_BACKTEST_OUTPUT,
    factor: Annotated[str, typer.Option(help="Factor name to backtest.")] = "momentum",
    refresh: Annotated[bool, typer.Option(help="Refresh data when panel is omitted.")] = False,
) -> None:
    """Run a factor backtest from a local OHLCV panel."""
    selected_factor = factor_preset or factor
    strategy_config = None
    if strategy is None:
        selected_factor = factor_preset or "risk_adjusted_momentum"
        strategy_config = get_factor_preset_config(selected_factor)

    panel_path = panel
    if panel_path is None:
        data_result = update_data_cache(
            universe_path=universe,
            start=start,
            end=end or date.today().isoformat(),
            adjust=adjust,
            cache_dir=cache_dir,
            artifacts_dir=output,
            refresh=refresh,
        )
        panel_path = data_result.panel_path

    result = run_factor_backtest(
        panel_path,
        strategy,
        output,
        factor_name=selected_factor,
        strategy_config=strategy_config,
    )
    typer.echo(f"equity: {result.equity_path}")
    typer.echo(f"trades: {result.trades_path}")
    typer.echo(f"summary: {result.summary_path}")
    typer.echo(f"report: {result.report_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
