# ML prediction report

```
test on unseen seeds [np.int64(7), np.int64(8)]  |  train rows 105,084  test rows 35,028
base rate (y=1 up on test): 0.533

model                        acc  bal_acc     auc      f1
--------------------------------------------------------
baseline_majority          0.533    0.500     nan   0.696
baseline_persistence       0.563    0.582     nan   0.421
logistic_observable        0.817    0.814   0.897   0.833
gbm_observable             0.814    0.811   0.897   0.833
gbm_oracle                 0.818    0.815   0.904   0.835
--------------------------------------------------------
observable edge over best baseline: +0.251  (>0 => learnable signal exists)
oracle lift over observable:        +0.004  (>0 => hidden latents add predictive power)
```
