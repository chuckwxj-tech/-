# P1 Category Cap Experiment

This report executes `docs/tasks/TASK-0011-category-cap.md`: add a same-category selection cap to the momentum target builder and compare no cap, cap 2, and cap 1.

## Setup

- Universe: 253 active A-share equity ETFs, commodity gold ETFs removed.
- Date range: 2023-06-30 to 2026-06-30.
- Data source: prior Futu QFQ panel in `artifacts/broad_etf_200_biweekly_top3_v3_no_gold/panel_qfq_no_gold.csv`.
- Momentum score: 20/60/120/240-day weighted return, volatility-adjusted by 60-day annualized volatility.
- Trend filter: off, matching the broad-pool baseline after P0 showed MA120 did not help.
- Rebalance: biweekly top3, next trading day open execution.
- Costs: 2.5 bps commission plus 5.0 bps slippage.
- Cash sleeve: residual cash accrues 1.5% annual yield.
- Category metadata: static ETF category from the 253-ETF universe file. Unknown category count: 0.
- Benchmark: prior accepted valid-pool equal-weight benchmark from `docs/results/broad_etf_200_biweekly_top3_20260630/summary.json`.

## Results

| Scenario | Total Return | CAGR | Volatility | Max Drawdown | Sharpe | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| No category cap | 104.71% | 28.23% | 33.31% | -38.72% | 0.914 | 0.729 |
| Category cap 2 | 97.13% | 26.56% | 32.57% | -37.98% | 0.887 | 0.699 |
| Category cap 1 | 90.29% | 25.02% | 30.45% | -35.54% | 0.887 | 0.704 |
| Benchmark: equal-weight valid pool ex-gold | 75.94% | 21.67% | 22.48% | -25.32% | 0.986 | 0.856 |

## Readout

The category cap works mechanically, but category capping alone on the current top3 strategy does not pass the strategy acceptance target.

- Max drawdown improves from `-38.72%` to `-37.98%` with cap 2 and `-35.54%` with cap 1.
- Sharpe falls from `0.914` to `0.887` under both caps, still below the benchmark `0.986`.
- Calmar remains below the benchmark `0.856`.

Latest 2026-06-26 signal:

| Scenario | Symbols | Categories |
|---|---|---|
| No category cap | `562590`, `588170`, `588710` | Semiconductor/chips, semiconductor/chips, semiconductor/chips |
| Category cap 2 | `588020`, `588170`, `588710` | Broad/size, semiconductor/chips, semiconductor/chips |
| Category cap 1 | `515050`, `588020`, `588710` | Communications/5G, broad/size, semiconductor/chips |

## Files

- `docs/results/p1_category_cap_20260630/summary.json`
- `docs/results/p1_category_cap_20260630/scenario_summary.csv`
- `docs/results/p1_category_cap_20260630/equity.csv`
- `docs/results/p1_category_cap_20260630/rebalance_selections.csv`
- `docs/results/p1_category_cap_20260630/experiment_config.json`

## Next Recommendation

Keep `max_per_category` as a risk-control parameter, but do not treat it as sufficient by itself. The remaining P1 items, especially top5/top8 comparison, should be tested next because a wider basket is likely needed before the category cap can materially improve risk-adjusted returns.
