# ML prediction report

Simulator v4; 20-tick forecasts. Synthetic data only.
Training seeds [1, 2, 3, 4, 5]; calibration [6]; unseen test [7, 8].
Rows: 87,630 training, 882 thinned calibration, 35,052 test.

| Direction model | Accuracy | Balanced accuracy | AUC |
|---|---:|---:|---:|
| baseline_majority | 0.523 | 0.500 | — |
| baseline_persistence | 0.552 | 0.538 | — |
| gbm_observable | 0.695 | 0.694 | 0.766 |
| gbm_calibrated | 0.696 | 0.694 | 0.766 |
| gbm_oracle | 0.694 | 0.693 | 0.767 |

Price MAE: **$0.868**; unchanged-price baseline: **$0.989**.
Price RMSE: $1.647. Return MAE: 110.4 bps (baseline 126.6 bps).
Nominal 80% interval: measured coverage **79.6%**, mean width 330.1 bps.

Up probability calibration: **platt**, chosen by two-fold time-split Brier on calibration seed [6] (uncalibrated 0.1977, platt 0.2011, isotonic 0.2035); refit on that seed only.
Test Brier: uncalibrated **0.1965**, calibrated **0.1966**. Test rows at or above the 62% entry threshold: 31.9% uncalibrated, 27.3% calibrated.

| Reliability (test) | Bin | Rows | Mean probability | Observed up rate |
|---|---|---:|---:|---:|
| uncalibrated | 0.0-0.1 | 2,453 | 0.055 | 0.071 |
| uncalibrated | 0.1-0.2 | 2,829 | 0.148 | 0.157 |
| uncalibrated | 0.2-0.3 | 3,186 | 0.253 | 0.241 |
| uncalibrated | 0.3-0.4 | 4,580 | 0.352 | 0.353 |
| uncalibrated | 0.4-0.5 | 5,198 | 0.450 | 0.441 |
| uncalibrated | 0.5-0.6 | 4,698 | 0.549 | 0.545 |
| uncalibrated | 0.6-0.7 | 4,367 | 0.649 | 0.643 |
| uncalibrated | 0.7-0.8 | 3,982 | 0.750 | 0.734 |
| uncalibrated | 0.8-0.9 | 3,019 | 0.842 | 0.808 |
| uncalibrated | 0.9-1.0 | 740 | 0.931 | 0.914 |
| calibrated | 0.0-0.1 | 2,130 | 0.057 | 0.062 |
| calibrated | 0.1-0.2 | 3,000 | 0.148 | 0.153 |
| calibrated | 0.2-0.3 | 3,505 | 0.253 | 0.240 |
| calibrated | 0.3-0.4 | 5,186 | 0.352 | 0.362 |
| calibrated | 0.4-0.5 | 5,680 | 0.449 | 0.456 |
| calibrated | 0.5-0.6 | 4,971 | 0.548 | 0.579 |
| calibrated | 0.6-0.7 | 4,357 | 0.648 | 0.685 |
| calibrated | 0.7-0.8 | 3,927 | 0.749 | 0.754 |
| calibrated | 0.8-0.9 | 1,930 | 0.840 | 0.844 |
| calibrated | 0.9-1.0 | 366 | 0.930 | 0.959 |

One-share long-only quote replay: 895 closed trades, realized net P&L **$-8.14**, mean net return -0.8 bps/trade, win rate 52.1%.
Entry at next-tick ask; exit at horizon bid or the next available bid; 1.0 bps fee each side. No overlapping positions per symbol.
Delayed exits: 47; positions still open: 0 (unrealized P&L at final last price: $0.00; not guaranteed executable).

These are simulator benchmarks, not evidence of real-market performance. Interval coverage is empirical, not guaranteed under new regimes. Calibrated probabilities are empirical on one calibration seed, not probabilities of profitable execution. Quote replay assumes one share can fill at recorded quotes, without changing subsequent market behavior; it is not a scalable execution backtest. Test labels overlap, so row count is not an independent sample count.

The saved model uses only training seeds; the interval pad and probability calibrator use only the calibration seed; test markets are never fitted. Agent emotions, campaign phases and live intrinsic value are oracle-only features.

Method references: [scikit-learn quantile regression](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), [time-ordered evaluation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).
