# Funded-agent evaluation · market v4

**24 funded experiments: 19 profitable Atlas accounts, 5 losing accounts, no flat accounts.**
All Atlas positions closed through actual fills. Mean net return: **+0.94%**.
The worst run lost **$2,274.99**. These are synthetic results, not real-market validation.

Buy-and-hold retained inventory in two runs. Of the 22 fully liquidated paired
comparisons, Atlas beat it in 14. Agent profit/loss counts include all 24 runs,
including the losing run whose benchmark could not liquidate.

| Scenario | Seed | Atlas cash P&L | Buy & hold P&L | Benchmark inventory |
|---|---:|---:|---:|---|
| Balanced | 501 | -720.24 | -6,009.51 | Closed |
| Balanced | 502 | +760.91 | -185.38 | Closed |
| Balanced | 503 | +999.29 | -3,634.24 | Closed |
| Balanced | 504 | +4,994.33 | -4,650.30 | Closed |
| Balanced | 505 | -347.57 | -1,072.09 | Closed |
| Balanced | 506 | +205.54 | -4,318.58 | Closed |
| Balanced | 507 | -2,274.99 | +1,271.95 | Closed |
| Balanced | 508 | +648.55 | +468.56 | Closed |
| Volatile | 501 | +2,217.64 | -1,270.13 | Closed |
| Volatile | 502 | +1,965.19 | +4,812.00 | Closed |
| Volatile | 503 | +5,366.81 | -4,404.38 | Closed |
| Volatile | 504 | +61.27 | +3,070.75 | Closed |
| Volatile | 505 | +38.27 | -16,300.31 | Closed |
| Volatile | 506 | -81.08 | -5,005.38 | Closed |
| Volatile | 507 | +1,472.86 | +2,167.57 | Closed |
| Volatile | 508 | +705.16 | +2,435.66 | Closed |
| Retail | 501 | +1,946.41 | -7,206.61 | Closed |
| Retail | 502 | +501.88 | +812.85 | Closed |
| Retail | 503 | -575.33 | -5,044.06 | Open, marked value |
| Retail | 504 | +1,157.27 | -4,505.85 | Open, marked value |
| Retail | 505 | +2,777.10 | +575.14 | Closed |
| Retail | 506 | +292.17 | -4,492.68 | Closed |
| Retail | 507 | +146.25 | +473.65 | Closed |
| Retail | 508 | +311.30 | +489.76 | Closed |

## Method

Eight fresh seeds, 501–508, each run in balanced, volatile, and retail-heavy
markets. Each account started with $100,000. Runs used 60 warmup ticks and 1,500
trading ticks, followed by up to 100 actual liquidation ticks. Atlas policy
settings were unchanged from the original arena: 62% up threshold, 20 bps edge
after estimated costs, 25 bps entry slippage allowance, 20% position cap,
60% exposure cap, 25% displayed-depth participation, 2.5% position stop, and
8% drawdown trigger. No borrowing, shorting, or manual intervention.

Orders use the shared exchange, delayed by one tick. Entry limits may fill
partially or not at all; sells sweep actual bids. Fees are 1 bp per side.
Benchmark buys equal target allocations without forecast ranking. Its remaining
inventory is reported instead of converted to artificial cash.

The model was trained on simulator-v4 seeds 1–5, calibrated on seed 6, and tested
on 7–8. Seeds 301–303 were development diagnostics. Seeds 401–408 evaluated a
rejected v3 candidate. The final seeds 501–508 were first run after the v4
mechanics, training, and policy settings were fixed. No result was dropped.

Model SHA256 prefix: `ccb7cf6b4d6d7415`. Simulator v4; policy v1.

## Reproduce

From `backend/`, with the existing virtual environment active:

```bash
OMP_NUM_THREADS=1 python -m app.evaluate \
  --seeds 501 502 503 504 505 506 507 508 \
  --scenarios balanced volatile retail --ticks 1500
```

[Raw results](agent-evaluation.json) include every outcome and settings.
[The audit](realism-audit.md) explains the identified simulator shortcuts,
rejected candidate, causal checks, and remaining limitations. These are eight
seeds across three scenarios, not 24 independent observations. Returns are not
annualized and no real-world profitability claim follows from them.

## Exact archived runs

- balanced / seed 501: `ebbe69a5aeba`
- balanced / seed 502: `97ebcda57bb1`
- balanced / seed 503: `0bba8160e7f7`
- balanced / seed 504: `f2bd59487ae6`
- balanced / seed 505: `5c34a85fae2f`
- balanced / seed 506: `a33871f4c904`
- balanced / seed 507: `ee903e5d6f76`
- balanced / seed 508: `a4ba151ec50e`
- volatile / seed 501: `cd892c52f6b4`
- volatile / seed 502: `ad253c9ba635`
- volatile / seed 503: `75c4cb8eb466`
- volatile / seed 504: `54b0047a1af7`
- volatile / seed 505: `f52f85c1977a`
- volatile / seed 506: `de362ff2334f`
- volatile / seed 507: `71765a1ff7c0`
- volatile / seed 508: `6d9724e2c266`
- retail / seed 501: `fe4aa7cecd31`
- retail / seed 502: `901c9033a67f`
- retail / seed 503: `bdf160538b59`
- retail / seed 504: `24bf931b22bb`
- retail / seed 505: `0a5418ccd3ee`
- retail / seed 506: `2dcb589c4045`
- retail / seed 507: `59c4dc5fa079`
- retail / seed 508: `9153430184f6`
