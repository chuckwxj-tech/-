# P0 Trend Filter and Cash Sleeve Experiment

This report executes the P0 items in `docs/EXPERIMENTS_TODO.md` against the same broad ETF pool used by `docs/BROAD_ETF_200_BIWEEKLY_TOP3_20260630.md`.

## Setup

- Universe: 253 active A-share equity ETFs, commodity gold ETFs removed.
- Date range: 2023-06-30 to 2026-06-30.
- Data source: prior Futu QFQ panel in `artifacts/broad_etf_200_biweekly_top3_v3_no_gold/panel_qfq_no_gold.csv`.
- Momentum score: 20/60/120/240-day weighted return, volatility-adjusted by 60-day annualized volatility.
- Rebalance: biweekly top 3, next trading day open execution.
- Costs: 2.5 bps commission plus 5.0 bps slippage.
- Cash sleeve: unfilled target slots remain in cash and accrue 1.5% annual yield.
- Benchmark: prior accepted valid-pool equal-weight benchmark from `docs/results/broad_etf_200_biweekly_top3_20260630/summary.json`.

## Results

| Scenario | Total Return | CAGR | Volatility | Max Drawdown | Sharpe | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| No trend filter top3 | 104.71% | 28.23% | 33.31% | -38.72% | 0.914 | 0.729 |
| MA120 filter + cash top3 | 102.43% | 27.73% | 33.39% | -38.72% | 0.901 | 0.716 |
| Benchmark: equal-weight valid pool ex-gold | 75.94% | 21.67% | 22.48% | -25.32% | 0.986 | 0.856 |

## Readout

P0 did not pass the stated acceptance target. MA120 + cash did not reduce the max drawdown versus the no-filter run, and Sharpe fell from 0.914 to 0.901. Both remain below the benchmark Sharpe of 0.986 and benchmark Calmar of 0.856.

The reason is that the MA120 filter barely constrained this universe over the test window. Across 77 rebalance signals, the MA120 cash scenario had 0 all-cash rebalances and only 2 partial-cash rebalances. The average target cash weight was 1.30%, and the latest 2026-06-26 signal remained fully invested in three semiconductor ETFs: `562590`, `588170`, `588710`.

## Files

- `docs/results/p0_trend_cash_20260630/summary.json`
- `docs/results/p0_trend_cash_20260630/equity.csv`
- `docs/results/p0_trend_cash_20260630/experiment_config.json`
- `docs/results/p0_trend_cash_20260630/no_trend_filter_rebalance_selections.csv`
- `docs/results/p0_trend_cash_20260630/ma120_cash_rebalance_selections.csv`

## Next Recommendation

Move to P1 before further signal tuning: compare top5/top8, add a same-category cap, and reduce `max_weight`. The current failure mode is concentration, not lack of a trend filter.
