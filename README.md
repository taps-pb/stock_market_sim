# Stock Market Simulator

An interactive market for six fictional stocks, driven by about 200 traders
plus market makers. Prices come from matched orders in a continuous double
auction. The human trades in the same book.

The AI forecasts **the price 20 ticks ahead**, an **80% forecast interval**, and
the probability of a higher close. A trained model is included. All prices,
companies, training data, and benchmark results are simulated.

## Run

Backend (port 8000):

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
OMP_NUM_THREADS=1 uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend (port 5173, proxies `/api` and `/ws`):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Forecasts appear after 60 ticks of history, about
15 seconds at the default clock. Accuracy and price error appear only after
predictions mature. The simulation keeps running without a browser connected.

## Market mechanics

- Price-time priority, partial fills, market sweeps, and self-trade prevention.
- Cash and shares reserved for outstanding orders; market buys checked against
  executable prices across the book, including fees. No human or retail shorting.
- Human limit orders remain open until filled or cancelled from the portfolio.
  Bot quotes expire; market makers replace theirs each tick.
- A fee of 1 basis point per side, collected by the simulated exchange. News
  orders come from a finite funded account: trades conserve cash and shares.
- Institutional campaigns, value investors, momentum traders, and emotional
  retail behavior. Institutions and market makers have bounded short capacity.
- Shared market/sector fundamental shocks, calm/stressed volatility states,
  staggered earnings, and public news revisions. Market makers widen spreads
  and reduce quote sizes when observed volatility rises.

The UI includes candles, forecast price levels, depth, trade tape, portfolio,
order cancellation, participant groups, and sentiment. Campaign phases and
agent emotions are educational simulator insights; they are **excluded from
production model inputs**. The trade ticket shows published valuation rather
than hidden live intrinsic value.

## Train and evaluate

From `backend/`, with the virtual environment active:

```bash
python -m ml.record --seeds 8 --ticks 3000 --horizon 20
OMP_NUM_THREADS=1 python -m ml.train --save ml/model.pkl
```

Restart the backend after replacing the model. Regenerate data and retrain after
changing market mechanics or calibration. Version-incompatible artifacts are
rejected, with the reason logged; the market can still run without forecasts.

The installed gradient-boosted model uses five training seeds, a separate seed
for interval calibration, and two untouched test seeds. Features use past price,
book depth, signed flow, and published valuation. Targets include future price
and return. The saved forecast horizon is independent of candle aggregation.

Current unseen-seed results on 35,052 test rows:

| Measure | Model | Baseline / target |
|---|---:|---:|
| Price mean absolute error | $0.601 | $1.032, unchanged price |
| Direction accuracy (up vs non-up) | 87.3% | 61.4%, last-move persistence |
| Interval coverage | 79.1% | 80% nominal |

See [the generated report](backend/ml/report.md) for the exact split, oracle
comparison, and a one-share trade replay using next-tick asks, exit bids, fees,
and delayed exits when liquidity disappears. Live metrics score matured calls
without using their outcomes during prediction.

These results measure learning inside this simulator. They do not establish
real-market predictive power or guaranteed trading returns. The market is still
highly learnable; realism has not been calibrated against real exchange data.

## Tests

```bash
cd backend
. .venv/bin/activate
OMP_NUM_THREADS=1 python -m pytest tests -q
```

From `frontend/`:

```bash
npm test
npm run build
```

Checks cover matching, trader behavior, capital conservation, reservations,
execution costs, exact future labels, feature parity, disjoint market splits,
forecast maturity, and WebSocket cleanup.

## Layout and tuning

- `backend/app/engine/`: matching, traders, fundamentals, simulation loop.
- `backend/app/api/`: REST and WebSocket routes.
- `backend/ml/`: data recording, quantile price models, evaluation, live serving.
- `frontend/src/`: React/TypeScript, Zustand, lightweight-charts.
- `backend/app/config.py`: seed companies, RNG seed, population, fees, regime
  dynamics, news, liquidity, and timing knobs.

State is in memory; restarting resets the market and portfolio. This remains a
single-user local sandbox, without authentication, portfolio persistence, a
full margin/borrow system, or real-market data. See [PROJECT.md](PROJECT.md) for
implementation context and remaining work.
