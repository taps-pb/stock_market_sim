"""Batch live price forecasts and score only predictions whose horizon has elapsed."""
from __future__ import annotations

from collections import deque
from hashlib import sha256
from pathlib import Path

import joblib
import numpy as np

from app.config import SIM_VERSION
from .features import HISTORY, OBSERVABLE_COLS, observable_row
from .train import SCHEMA_VERSION, forecast


class Predictor:
    def __init__(self, path: str) -> None:
        self.fingerprint = sha256(Path(path).read_bytes()).hexdigest()[:16]
        self.artifact = joblib.load(path)
        d = self.artifact
        if (d.get("schema_version") != SCHEMA_VERSION or d.get("sim_version") != SIM_VERSION
                or d.get("cols") != OBSERVABLE_COLS or not isinstance(d.get("horizon"), int)
                or d["horizon"] < 1):
            raise ValueError("incompatible model; regenerate data and retrain")
        self.model = d["model"]
        self.cols = d["cols"]
        self.horizon = d["horizon"]
        self.buf: dict[str, deque] = {}
        self.pending: deque = deque()
        self.hits = self.total = self.covered = 0
        self.error = self.baseline_error = 0.0
        self.last_tick: int | None = None
        self.last_output: dict = {}
        self.by_symbol: dict[str, dict] = {}
        self.recent: deque = deque(maxlen=120)

    def _vector(self, engine, s: str) -> list[float]:
        row = observable_row(np.array(self.buf[s], dtype=float),
                             engine.books[s].depth(8), engine.books[s].spread(),
                             engine.flow[s], engine.companies[s].public_fair())
        return [row[c] for c in self.cols]

    def step(self, engine) -> dict:
        if engine.tick == self.last_tick:
            return self.last_output
        if self.last_tick is not None and engine.tick != self.last_tick + 1:
            # Gaps invalidate lag features and exact-horizon scoring.
            self.buf.clear()
            self.pending.clear()
            self.hits = self.total = self.covered = 0
            self.error = self.baseline_error = 0.0
            self.by_symbol.clear()
            self.recent.clear()
        self.last_tick = engine.tick
        for s in engine.symbols:
            self.buf.setdefault(s, deque(maxlen=HISTORY)).append(engine.last[s])
        while self.pending and self.pending[0][0] <= engine.tick:
            tick, s, up, initial, predicted, lower, upper = self.pending.popleft()
            if tick != engine.tick:
                continue
            actual = engine.last[s]
            err = abs(actual - predicted)
            baseline_err = abs(actual - initial)
            hit = int(lower <= actual <= upper)
            self.hits += int((actual > initial) == up)
            self.covered += hit
            self.error += err
            self.baseline_error += baseline_err
            self.total += 1
            stats = self.by_symbol.setdefault(s, {"n": 0, "error": 0.0, "baseline_error": 0.0, "covered": 0})
            stats["n"] += 1
            stats["error"] += err
            stats["baseline_error"] += baseline_err
            stats["covered"] += hit
            self.recent.appendleft({"symbol": s, "issued_tick": tick - self.horizon, "target_tick": tick,
                                    "starting_price": initial, "predicted_price": predicted, "lower": lower,
                                    "upper": upper, "actual_price": actual, "abs_error": err, "covered": bool(hit)})

        symbols = [s for s in engine.symbols if len(self.buf[s]) >= HISTORY]
        signals = {}
        if symbols:
            x = np.array([self._vector(engine, s) for s in symbols])
            probs = self.model.predict_proba(x)[:, 1]
            returns, lows, highs = forecast(self.artifact, x)
            for s, p, ret, lo, hi in zip(symbols, probs, returns, lows, highs):
                initial = engine.last[s]
                predicted, lower, upper = (initial * (1 + r) for r in (ret, lo, hi))
                signals[s] = {"dir": "up" if p >= 0.5 else "down", "prob": round(float(p), 4),
                              "price": round(float(predicted), 2), "lower": round(float(lower), 2),
                              "upper": round(float(upper), 2), "return_pct": round(float(ret * 100), 3),
                              "target_tick": engine.tick + self.horizon}
                self.pending.append((engine.tick + self.horizon, s, p >= 0.5,
                                     initial, predicted, lower, upper))
        by_symbol = {}
        for s in engine.symbols:
            stats = self.by_symbol.get(s)
            n = stats["n"] if stats else 0
            by_symbol[s] = {"n": n,
                            "mae": stats["error"] / n if n else None,
                            "baseline_mae": stats["baseline_error"] / n if n else None,
                            "coverage": stats["covered"] / n if n else None}
        self.last_output = {
            "signals": signals, "accuracy": self.hits / self.total if self.total else None,
            "mae": self.error / self.total if self.total else None,
            "baseline_mae": self.baseline_error / self.total if self.total else None,
            "coverage": self.covered / self.total if self.total else None,
            "interval_coverage": self.artifact["interval_coverage"],
            "evaluation": self.artifact["evaluation"],
            "n": self.total, "horizon": self.horizon,
            "review": {"by_symbol": by_symbol, "recent": list(self.recent)},
        }
        return self.last_output
