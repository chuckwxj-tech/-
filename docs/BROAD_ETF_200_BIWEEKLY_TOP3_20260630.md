# Broad ETF Biweekly Top-3 Momentum Backtest

## Scope

This report records a broad-pool ETF momentum backtest run on 2026-06-30.

- Universe source: AKShare current active ETF list, joined with Futu OpenD QFQ daily bars.
- Candidate pool after name filters: 1,223 equity ETF candidates.
- Valid Futu QFQ history pool: 260 ETFs.
- Final pool after removing commodity gold ETFs: 253 ETFs.
- Backtest range: 2023-06-30 to 2026-06-30.
- Rebalance rule: every two weeks, buy the top 3 momentum ETFs, equal weight.
- Execution rule: next trading day open.
- Cost assumption: 2.5 bps commission plus 5.0 bps slippage.

## Signal

The momentum score is:

```text
(0.2 * 20d return + 0.4 * 60d return + 0.3 * 120d return + 0.1 * 240d return)
/ 60d annualized volatility
```

This run uses pure top-3 ranking with no MA120 trend filter.

## Results

| Metric | Strategy |
|---|---:|
| Initial equity | 1,000,000 |
| Final equity | 2,046,254.47 |
| Total return | 104.63% |
| CAGR | 28.21% |
| Annualized volatility | 33.32% |
| Max drawdown | -38.72% |
| Max drawdown start | 2024-11-07 |
| Max drawdown trough | 2025-04-07 |
| Max drawdown recovery | 2026-01-28 |
| Sharpe | 0.91 |
| Calmar | 0.73 |
| Trades | 331 |
| Rebalance signals | 77 |

Benchmark:

| Benchmark | Total return | CAGR | Annualized volatility | Max drawdown | Sharpe | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| Equal-weight valid pool, excluding gold ETFs | 75.94% | 21.67% | 22.48% | -25.32% | 0.99 | 0.86 |

## Final Universe Distribution

| Category | ETFs |
|---|---:|
| Broad index / size | 87 |
| Semiconductor / chips | 24 |
| Dividend / low-vol / quality | 23 |
| Other equity themes | 21 |
| AI / robotics / computer | 20 |
| Financials / real estate | 17 |
| Healthcare | 17 |
| Consumer | 13 |
| New energy / electrical equipment | 12 |
| Cyclicals / resources | 11 |
| Communications / 5G | 4 |
| Defense | 4 |

## Selection Concentration

| Category | Selected count |
|---|---:|
| Financials / real estate | 65 |
| Communications / 5G | 29 |
| Dividend / low-vol / quality | 27 |
| Broad index / size | 26 |
| Semiconductor / chips | 23 |
| Cyclicals / resources | 21 |
| Other equity themes | 14 |
| New energy / electrical equipment | 11 |
| Healthcare | 7 |
| AI / robotics / computer | 5 |
| Consumer | 3 |

Most frequently selected ETFs:

| Symbol | Name | Category | Selected count |
|---|---|---|---:|
| 516310 | 银行ETF易方达 | Financials / real estate | 19 |
| 515450 | 红利低波50ETF南方 | Dividend / low-vol / quality | 16 |
| 515300 | 300红利低波ETF嘉实 | Broad index / size | 16 |
| 515290 | 银行ETF天弘 | Financials / real estate | 14 |
| 515880 | 通信ETF国泰 | Communications / 5G | 13 |
| 512800 | 银行ETF华宝 | Financials / real estate | 11 |

Latest signal as of 2026-06-26:

| Rank | Symbol | Name | Category | Score |
|---:|---|---|---|---:|
| 1 | 588710 | 科创半导体设备ETF华泰柏瑞 | Semiconductor / chips | 2.2300 |
| 2 | 588170 | 科创半导体ETF华夏 | Semiconductor / chips | 2.2143 |
| 3 | 562590 | 半导体设备ETF华夏 | Semiconductor / chips | 2.1319 |

## Data Caveats

- This is a current-active-universe backtest, not a point-in-time historical ETF universe. Survivorship bias remains.
- Futu OpenD enforces a historical K-line rate limit. The data pull handled this by retrying after the 30-second window.
- Commodity gold ETFs were removed after the first wide-pool run because the requested test is for equity ETF industry/theme rotation.
- Raw daily history panels are not committed to git. The repository stores the compact result files under `docs/results/broad_etf_200_biweekly_top3_20260630/`.

## Result Files

- `docs/results/broad_etf_200_biweekly_top3_20260630/summary.json`
- `docs/results/broad_etf_200_biweekly_top3_20260630/equity.csv`
- `docs/results/broad_etf_200_biweekly_top3_20260630/rebalance_selections.csv`
- `docs/results/broad_etf_200_biweekly_top3_20260630/selection_counts_by_category.csv`
- `docs/results/broad_etf_200_biweekly_top3_20260630/selection_counts_by_etf.csv`
- `docs/results/broad_etf_200_biweekly_top3_20260630/valid_universe.csv`
- `docs/results/broad_etf_200_biweekly_top3_20260630/removed_gold_etfs.csv`
