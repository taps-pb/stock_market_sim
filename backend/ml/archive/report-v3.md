# ML prediction report

Simulator v3; 20-tick forecasts. Synthetic data only.
Training seeds [1, 2, 3, 4, 5]; calibration [6]; unseen test [7, 8].
Rows: 87,630 training, 882 thinned calibration, 35,052 test.

| Direction model | Accuracy | Balanced accuracy | AUC |
|---|---:|---:|---:|
| baseline_majority | 0.604 | 0.500 | — |
| baseline_persistence | 0.624 | 0.547 | — |
| gbm_observable | 0.747 | 0.727 | 0.826 |
| gbm_oracle | 0.755 | 0.740 | 0.839 |

Price MAE: **$0.946**; unchanged-price baseline: **$1.143**.
Price RMSE: $2.309. Return MAE: 121.6 bps (baseline 147.7 bps).
Nominal 80% interval: measured coverage **81.3%**, mean width 369.7 bps.

One-share long-only quote replay: 657 closed trades, realized net P&L **$213.76**, mean net return 47.1 bps/trade, win rate 53.7%.
Entry at next-tick ask; exit at horizon bid or the next available bid; 1.0 bps fee each side. No overlapping positions per symbol.
Delayed exits: 46; positions still open: 0 (unrealized P&L at final last price: $0.00; not guaranteed executable).

These are simulator benchmarks, not evidence of real-market performance. Interval coverage is empirical, not guaranteed under new regimes. Direction probabilities are uncalibrated classifier estimates. Quote replay assumes one share can fill at recorded quotes, without changing subsequent market behavior; it is not a scalable execution backtest. Test labels overlap, so row count is not an independent sample count.

The saved model uses only training seeds; calibration and test markets are never fitted. Agent emotions, campaign phases and live intrinsic value are oracle-only features.

Method references: [scikit-learn quantile regression](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), [time-ordered evaluation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).
