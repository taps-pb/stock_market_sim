# Funded-agent evaluation

All nine runs settled completely. Atlas was profitable after fees in all nine,
and beat buy-and-hold in five. Mean Atlas return was **+1.58%**; mean buy-and-hold
return was **+2.53%**. Mean excess profit was **−$949.77** per $100,000 account.
A profitable strategy did not produce the highest average return in this sample.

| Scenario | Seed | Atlas net P&L | Buy & hold net P&L | Excess P&L | Atlas max drawdown |
|---|---:|---:|---:|---:|---:|
| Balanced | 101 | $+1,701.96 | $+1,479.86 | $+222.10 | 0.020% |
| Balanced | 102 | $+1,852.12 | $+981.43 | $+870.69 | 0.025% |
| Balanced | 103 | $+1,703.44 | $-1,637.91 | $+3,341.35 | 0.026% |
| Volatile | 101 | $+1,370.95 | $+5,354.17 | $-3,983.22 | 0.307% |
| Volatile | 102 | $+1,491.26 | $-3,267.56 | $+4,758.82 | 0.051% |
| Volatile | 103 | $+1,810.84 | $+12,464.83 | $-10,653.99 | 0.029% |
| Retail | 101 | $+1,722.82 | $+3,387.27 | $-1,664.45 | 0.025% |
| Retail | 102 | $+1,222.20 | $+1,172.86 | $+49.34 | 0.020% |
| Retail | 103 | $+1,352.03 | $+2,840.61 | $-1,488.58 | 0.034% |

## Method

- Three fresh seeds, 101–103, each run in balanced, volatile, and retail-heavy
  environments. These seeds are outside model training/calibration/testing (1–8).
- $100,000 starting cash for each account; 60 warmup ticks, 1,500 trading ticks,
  followed by actual liquidation. All final positions were zero.
- Default Atlas policy: 62% minimum up estimate, 20 bps minimum edge after
  estimated costs, 25 bps entry slippage allowance, 20% single-position cap,
  60% total exposure cap, 25% displayed-depth participation, 2.5% position stop,
  8% drawdown stop. Long-only, no borrowing.
- Both funded accounts place next-tick orders into the same exchange as NPCs.
  Partial/zero fills, available cash, spreads, market impact, and 1 bp per-side
  fees affect realized outcomes. No mark-to-market liquidation substitutes.
- Buy-and-hold builds equal target allocations using 60% of starting capital,
  independent of AI forecast ranking, and holds until settlement. Cash is the
  second baseline. No manual orders were submitted in these nine runs.
- Model SHA256 prefix: `c886a66255b844af`. No model retraining or policy tuning
  used these outcomes. Earlier development runs remain in the local archive;
  the final report's run IDs are listed below and in the JSON.

## Reproduce

From `backend/`, with the existing virtual environment active:

```bash
OMP_NUM_THREADS=1 python -m app.evaluate \
  --seeds 101 102 103 --scenarios balanced volatile retail --ticks 1500
```

The command stores every result in SQLite and writes
[agent-evaluation.json](agent-evaluation.json). New run IDs and timestamps are
expected; with identical code, settings, and model, fills and balances reproduce.

## Interpretation

This is an execution-valid experiment inside a synthetic market, not evidence
of real-world trading skill. The NPCs leave persistent patterns that the model
can learn. Small observed drawdowns partly reflect conservative position sizes
and short holding periods; they do not imply guaranteed downside protection.
Buy-and-hold generally has greater sustained exposure, so raw return comparisons
are not risk-matched. Both accounts also influence the market they share.

There are only three seeds reused across three scenarios, not nine independent
real-world markets. Tick returns cannot be annualized meaningfully. No real-data
calibration, transaction tax, borrow cost, dividends, or venue latency is modeled.
Do not infer statistical significance from nine profitable runs. Calibration
against real market behavior is the next requirement for stronger realism claims.

## Exact archived runs

- balanced / seed 101: `1f5cad576b14`
- balanced / seed 102: `1de0367e4cc0`
- balanced / seed 103: `79321468581c`
- volatile / seed 101: `fb706ba56507`
- volatile / seed 102: `ebd337439359`
- volatile / seed 103: `02c0278ef17b`
- retail / seed 101: `cfaee76d4ea0`
- retail / seed 102: `b9ecd57f416d`
- retail / seed 103: `12fbb45b71ed`
