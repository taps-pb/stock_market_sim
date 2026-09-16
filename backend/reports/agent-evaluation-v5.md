# Funded-agent evaluation · market v4, model v5 calibration, tuned policy

## What changed vs v4

| | v4 report | v5 report |
|---|---|---|
| Model | `ccb7cf6b4d6d7415`, raw classifier probability | `ab59356cf67d9b26`: same classifier, quantiles and interval, plus Platt calibration fit on seed 6 only |
| Policy | p ≥ 0.62, edge ≥ 20 bps, position ≤ 20% | p ≥ 0.62, **edge ≥ 0 bps**, **position ≤ 30%** |
| Selection | Settings fixed before final seeds | 27-point grid on tuning seeds 601–612 (3 scenarios, 972 runs); score = mean excess return − 0.5 × mean Atlas drawdown. Seeds 501–508 not used for selection |
| Statistics | Counts only | Seed-bootstrap 95% CIs and sign tests |

Everything else is unchanged: simulator v4, 60% exposure cap, 25 bps slippage allowance, 25% depth participation,
2.5% position stop, 8% drawdown trigger, 1,500 ticks, $100,000 per account.

Calibration barely changed the probabilities. On calibration seed 6 (two-fold time split), raw Brier was 0.1977, Platt 0.2011,
isotonic 0.2035. On test seeds 7–8, Brier went from 0.1965 to 0.1966. The raw classifier was already close to calibrated; see
[`ml/report.md`](../ml/report.md). Platt was used because the task required a calibrator, not because it improved calibration.

The tuning surface is noisy. Scores do not change smoothly with the settings. The v4 settings scored 1.04 and ranked 18th of 27; the chosen
point scored 1.59, with 1.41 and 1.40 next. Treat the choice as weakly supported. See [`policy-tuning-v5.json`](policy-tuning-v5.json).

## Final seeds 501–508: v4, calibration only, and v5

| Seeds 501–508 × 3 scenarios | v4 | Calibrated model, v4 policy | v5 (calibrated + tuned) |
|---|---:|---:|---:|
| Profitable / losing Atlas runs | 19 / 5 | 18 / 6 | 16 / 8 |
| Mean Atlas return (95% CI) | +0.94% (+0.44 to +1.47) | +0.74% (+0.22 to +1.27) | +1.14% (+0.23 to +2.04) |
| Mean excess vs buy-and-hold (95% CI) | +2.91% (+0.59 to +5.26) | +2.63% (+0.29 to +4.94) | +3.01% (+0.80 to +5.45) |
| Beat hold, fully liquidated pairs | 14 / 22 | 13 / 23 | 15 / 21 |
| Sign test on per-seed mean excess, p | 0.727 (5+/3−) | 0.727 (5+/3−) | 0.289 (6+/2−) |
| Worst Atlas run | −$2,274.99 | see ablation JSON | −$4,344.58 |

v4 statistics were recomputed from the unchanged v4 JSON using the same code. The calibration-only column is an ablation
run after the v5 settings were already chosen and committed. It was not used for selection; see
[`agent-evaluation-v5-ablation.json`](agent-evaluation-v5-ablation.json).

**Interpretation.** Calibration alone slightly lowered mean return on these seeds. The tuned policy raised the mean return
and mean excess, but it also took larger positions. There were more losing runs (8 vs 5), a larger worst loss, and a wider CI. Every
difference between columns is well inside the overlapping CIs. With 8 seeds, this does not show that v5 is better than v4.
Every CI is above zero, but the bootstrap has only 8 seed clusters, and the sign tests are not significant.

## v5 results

**24 runs: 16 profitable, 8 losing, 0 flat Atlas accounts (24 fully liquidated).** Atlas beat buy-and-hold in 15 of 21 fully liquidated paired comparisons.

| Statistic | Value |
|---|---|
| Mean Atlas return | +1.14% (95% CI +0.23% to +2.04%) |
| Mean Atlas minus buy-and-hold return | +3.01% (95% CI +0.80% to +5.45%) |
| Sign test on excess, per run | 15 positive, 6 negative, 0 ties; two-sided p = 0.078 |
| Sign test on excess, per-seed means | 6 positive, 2 negative, 0 ties; two-sided p = 0.289 |

Bootstrap: 10,000 draws resampling whole seeds (scenarios within a seed are dependent), fixed bootstrap seed 0. The per-run sign test treats dependent scenarios as independent; the per-seed test does not.

| Scenario | Seed | Atlas P&L | Buy & hold P&L | Excess return | Atlas drawdown | Benchmark inventory |
|---|---:|---:|---:|---:|---:|---|
| Balanced | 501 | -2,162.12 | -7,064.28 | +4.90% | 4.97% | Closed |
| Balanced | 502 | +76.91 | +354.11 | -0.28% | 1.71% | Closed |
| Balanced | 503 | -308.12 | -4,716.12 | +4.41% | 2.03% | Open, marked value |
| Balanced | 504 | +4,485.20 | -4,963.65 | +9.45% | 2.11% | Closed |
| Balanced | 505 | +2,511.90 | -1,244.00 | +3.76% | 0.75% | Closed |
| Balanced | 506 | +801.48 | -3,907.17 | +4.71% | 0.72% | Closed |
| Balanced | 507 | +2,592.19 | +1,206.24 | +1.39% | 1.16% | Closed |
| Balanced | 508 | +4,608.64 | +712.21 | +3.90% | 0.42% | Closed |
| Volatile | 501 | +823.11 | -2,155.40 | +2.98% | 1.79% | Closed |
| Volatile | 502 | +946.47 | +5,100.44 | -4.15% | 0.42% | Closed |
| Volatile | 503 | +7,449.63 | -4,041.74 | +11.49% | 1.26% | Closed |
| Volatile | 504 | -4,344.58 | +3,062.00 | -7.41% | 5.23% | Closed |
| Volatile | 505 | +669.80 | -16,206.50 | +16.88% | 1.08% | Closed |
| Volatile | 506 | -253.34 | -4,267.35 | +4.01% | 2.62% | Closed |
| Volatile | 507 | +346.89 | +2,249.23 | -1.90% | 2.53% | Closed |
| Volatile | 508 | +6,261.25 | +4,235.76 | +2.03% | 2.50% | Closed |
| Retail | 501 | -2,076.37 | -7,442.32 | +5.37% | 3.45% | Closed |
| Retail | 502 | +741.27 | +565.17 | +0.18% | 0.37% | Closed |
| Retail | 503 | -166.77 | -5,084.68 | +4.92% | 1.70% | Open, marked value |
| Retail | 504 | +1,229.55 | -3,950.50 | +5.18% | 0.17% | Open, marked value |
| Retail | 505 | +2,646.96 | +253.53 | +2.39% | 2.56% | Closed |
| Retail | 506 | +1,418.34 | -4,404.42 | +5.82% | 0.87% | Closed |
| Retail | 507 | -431.47 | +569.77 | -1.00% | 0.67% | Closed |
| Retail | 508 | -581.65 | +811.29 | -1.39% | 0.92% | Closed |

"Excess return" is Atlas net P&L minus buy-and-hold net P&L, divided by starting capital. Pairs where buy-and-hold kept open
inventory are left out of the paired statistics. Their marked values are shown only in the table.

## Reproduce

```bash
OMP_NUM_THREADS=1 python -m app.evaluate --tune --seeds 601 602 603 604 605 606 607 608 609 610 611 612 \
  --scenarios balanced volatile retail --ticks 1500 --workers 12 --out reports/policy-tuning-v5.json
OMP_NUM_THREADS=1 python -m app.evaluate --seeds 501 502 503 504 505 506 507 508 \
  --scenarios balanced volatile retail --ticks 1500 \
  --policy '{"min_probability": 0.62, "min_edge_bps": 0, "max_position": 0.3}' \
  --out reports/agent-evaluation-v5.json --markdown reports/agent-evaluation-v5-stats.md
```

These are synthetic markets. They are not evidence of real-market performance. Live `Experiment` defaults remain the v4 policy.
