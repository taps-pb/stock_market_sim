"""Live model serving: turn the current market state into per-symbol signals,
and score them against reality as the horizon matures (honest live accuracy).
"""
from __future__ import annotations

from collections import deque

import numpy as np

from .features import HISTORY, observable_row


class Predictor:
    def __init__(self, path: str) -> None:
        import joblib
        d = joblib.load(path)
        self.model = d["model"]
        self.cols = d["cols"]
        self.buf: dict[str, deque] = {}
        self.pending: deque = deque()        # (mature_tick, symbol, dir, price_at_call)
        self.hits = 0
        self.total = 0

    def _vector(self, engine, s: str) -> np.ndarray:
        row = observable_row(np.array(self.buf[s], dtype=float),
                             engine.books[s].depth(8), engine.books[s].spread(),
                             engine.flow[s], engine.companies[s].public_fair(),
                             engine._sentiment())
        return np.array([[row[c] for c in self.cols]])

    def step(self, engine) -> dict:
        """Call once per tick, after engine.step(). Returns signals + live accuracy."""
        H = engine.cfg.candle_ticks
        for s in engine.symbols:
            self.buf.setdefault(s, deque(maxlen=HISTORY)).append(engine.last[s])

        # score matured predictions against what actually happened
        while self.pending and self.pending[0][0] <= engine.tick:
            _, s, direction, px = self.pending.popleft()
            went_up = engine.last[s] > px
            self.hits += int(went_up == (direction == "up"))
            self.total += 1

        signals: dict[str, dict] = {}
        for s in engine.symbols:
            if len(self.buf[s]) < HISTORY:
                continue
            p = float(self.model.predict_proba(self._vector(engine, s))[0, 1])
            direction = "up" if p >= 0.5 else "down"
            signals[s] = {"dir": direction, "prob": round(p, 3)}
            self.pending.append((engine.tick + H, s, direction, engine.last[s]))

        acc = self.hits / self.total if self.total else None
        return {"signals": signals, "accuracy": round(acc, 3) if acc is not None else None,
                "n": self.total, "horizon": H}
