# Stock Market Simulator

A trader-driven stock market simulator. Prices are **not** computed from a
formula — they emerge from the collision of ~70 simulated traders with different
psychology (whales who buy the dip, retail who FOMO the top and panic-sell the
first red, momentum chasers, patient value buyers, weak hands, market makers,
noise) trading in a real continuous double-auction order book. The human is a
trader in the same book.

All fundamentals and prices are fictional and simulated.

## Layout

- `backend/` — Python + FastAPI. The sim engine (`app/engine/`) is the heart:
  order book + matching, trader traits + emotional state, per-tick loop. REST +
  WebSocket in `app/api/`.
- `frontend/` — Vite + React + TypeScript. Candlestick chart (lightweight-charts),
  watchlist, live order-book depth, time & sales, trade ticket, portfolio, and a
  fear/greed sentiment meter.

## Run

Backend (port 8000):

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Frontend (port 5173, proxies `/api` + `/ws` to the backend):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Tests

```bash
cd backend && . .venv/bin/activate && pytest tests -q
```

- `test_orderbook.py` — matching engine correctness (price-time priority, partial
  fills, market sweeps, cancels).
- `test_traders.py` — the psychology: weak hands panic on a small dip while whales
  buy it; FOMO chases a rally while value stays disciplined; the market reverts
  toward fair value and stays internally consistent.

## Tuning

All calibration knobs live in `backend/app/config.py`: archetype mix, trait
ranges, fear/greed dynamics, market-maker spread, fundamental drift, earnings
surprises, tick rate, RNG seed (fixed for reproducible runs). Seed companies are
the `SEED_COMPANIES` list in the same file — add rows to expand beyond the
starting six.
