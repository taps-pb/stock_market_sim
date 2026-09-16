# ML prediction report

Simulator v4; 20-tick forecasts. Synthetic data only.
Training seeds [1, 2, 3, 4, 5]; calibration [6]; unseen test [7, 8].
Rows: 87,630 training, 882 thinned calibration, 35,052 test.

| Direction model | Accuracy | Balanced accuracy | AUC |
|---|---:|---:|---:|
| baseline_majority | 0.523 | 0.500 | — |
| baseline_persistence | 0.552 | 0.538 | — |
| gbm_observable | 0.695 | 0.694 | 0.766 |
| gbm_oracle | 0.694 | 0.693 | 0.767 |

Price MAE: **$0.868**; unchanged-price baseline: **$0.989**.
Price RMSE: $1.647. Return MAE: 110.4 bps (baseline 126.6 bps).
Nominal 80% interval: measured coverage **79.6%**, mean width 330.1 bps.

One-share long-only quote replay: 895 closed trades, realized net P&L **$-8.14**, mean net return -0.8 bps/trade, win rate 52.1%.
Entry at next-tick ask; exit at horizon bid or the next available bid; 1.0 bps fee each side. No overlapping positions per symbol.
Delayed exits: 47; positions still open: 0 (unrealized P&L at final last price: $0.00; not guaranteed executable).

These are simulator benchmarks, not evidence of real-market performance. Interval coverage is empirical, not guaranteed under new regimes. Direction probabilities are uncalibrated classifier estimates. Quote replay assumes one share can fill at recorded quotes, without changing subsequent market behavior; it is not a scalable execution backtest. Test labels overlap, so row count is not an independent sample count.

The saved model uses only training seeds; calibration and test markets are never fitted. Agent emotions, campaign phases and live intrinsic value are oracle-only features.

Method references: [scikit-learn quantile regression](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), [time-ordered evaluation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).
