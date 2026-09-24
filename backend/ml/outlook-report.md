# Synthetic market outlook

20 / 60 / 120 simulation ticks; ticks have no calendar-time mapping.
The six-stock equal-weight normalized price index starts at 100 at tick 0 and is not tradable.
Stock models fit training seeds [1, 2, 3, 4, 5]; stock and index intervals calibrate on seeds [6].
All reported errors and coverage use unseen seeds [7, 8]. Calls overlap in time.

| Ticks | Stock MAE ($) | Stock baseline ($) | Stock coverage | Index MAE (points) | Index baseline (points) | Index coverage |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0.868 | 0.989 | 79.6% | 0.554 | 0.635 | 78.8% |
| 60 | 2.026 | 2.090 | 78.4% | 1.232 | 1.245 | 74.1% |
| 120 | 2.907 | 2.994 | 79.6% | 1.777 | 1.744 | 77.9% |
