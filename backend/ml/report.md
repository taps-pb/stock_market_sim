# ML prediction report

```
test on unseen seeds [np.int64(7), np.int64(8)]  |  train rows 105,084  test rows 35,028
base rate (y=1 up on test): 0.534

model                        acc  bal_acc     auc      f1
--------------------------------------------------------
baseline_majority          0.534    0.500     nan   0.696
baseline_persistence       0.572    0.591     nan   0.433
logistic_observable        0.830    0.826   0.906   0.847
gbm_observable             0.829    0.823   0.910   0.848
gbm_oracle                 0.830    0.825   0.913   0.849
--------------------------------------------------------
observable edge over best baseline: +0.257  (>0 => learnable signal exists)
oracle lift over observable:        +0.001  (>0 => hidden latents add predictive power)
```
