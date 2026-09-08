"""Funded trading experiments, real exchange execution, and durable run results."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from math import isfinite
import json
import sqlite3
from uuid import uuid4

from .agent import plan_orders
from .config import Config, SEED_COMPANIES, SIM_VERSION
from .engine.market import Order, Side
from .engine.simulation import SimEngine
from ml.features import HISTORY

AI_ID, HOLD_ID = "ATLAS", "HOLD"


@dataclass
class Experiment:
    seed: int = 42
    capital: float = 100_000
    duration: int = 1500
    scenario: str = "balanced"
    max_position: float = 0.20
    max_exposure: float = 0.60
    max_drawdown: float = 0.08
    stop_loss: float = 0.025
    min_probability: float = 0.62
    min_edge_bps: float = 20
    slippage_bps: float = 25
    participation: float = 0.25

    def __post_init__(self):
        ranges = {"capital": (1000, 1_000_000), "max_position": (.01, .30),
                  "max_exposure": (.1, .9), "max_drawdown": (.01, .30),
                  "stop_loss": (.005, .15), "min_probability": (.5, .95),
                  "min_edge_bps": (0, 200), "slippage_bps": (0, 100), "participation": (.01, .5)}
        for name, (low, high) in ranges.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high}")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be an integer between 0 and 4294967295")
        if type(self.duration) is not int or not 100 <= self.duration <= 10_000:
            raise ValueError("duration must be an integer between 100 and 10000 ticks")
        if self.scenario not in {"balanced", "volatile", "retail"}:
            raise ValueError("unknown market scenario")
        if self.max_position > self.max_exposure:
            raise ValueError("single-position limit cannot exceed total exposure")


class Arena:
    def __init__(self, settings: Experiment, predictor):
        self.settings = settings
        cfg = Config(seed=settings.seed)
        if settings.scenario == "volatile":
            cfg.news_prob, cfg.news_notional, cfg.stress_enter_prob = .25, 160_000, .02
        elif settings.scenario == "retail":
            cfg.mix = {**cfg.mix, "fomo": .40, "weak_hands": .25, "retail": .20}
        self.engine = SimEngine(cfg, SEED_COMPANIES)
        self.predictor = predictor
        self.id = uuid4().hex[:12]
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.status = "running" if predictor else "failed"
        self.error = None if predictor else "The trained model is unavailable. Regenerate data and train it before starting."
        self.agent_halted = False
        self.pending: list[tuple[str, dict]] = []
        self.decisions: list[dict] = []
        self.curve: list[dict] = []
        self.entry_ticks = {AI_ID: {}, HOLD_ID: {}}
        self.spent = {AI_ID: defaultdict(float), HOLD_ID: defaultdict(float)}
        self.peaks = {AI_ID: settings.capital, HOLD_ID: settings.capital}
        self.drawdowns = {AI_ID: 0.0, HOLD_ID: 0.0}
        self.last_seen = {AI_ID: 0, HOLD_ID: 0}
        self.settle_started: int | None = None
        self.archived = False
        self.model = None
        for tid in (AI_ID, HOLD_ID):
            self.engine.add_account(tid, settings.capital)
        self._record_curve()

    @property
    def terminal(self) -> bool:
        return self.status in {"completed", "failed", "interrupted"}

    def finish(self):
        if not self.terminal:
            self.status = "settling"
            self.settle_started = self.engine.tick
            self.pending = []
            self._plan(liquidate=True)

    def _equity(self, tid: str) -> float:
        trader = self.engine.by_id[tid]
        return trader.cash + sum(q * self.engine.last[s] for s, q in trader.positions.items())

    def _record_curve(self):
        values = {tid: self._equity(tid) for tid in (AI_ID, HOLD_ID)}
        for tid, value in values.items():
            self.peaks[tid] = max(self.peaks[tid], value)
            self.drawdowns[tid] = max(self.drawdowns[tid], 1 - value / self.peaks[tid])
        point = {"tick": self.engine.tick, "agent": round(values[AI_ID], 2),
                 "hold": round(values[HOLD_ID], 2), "cash": self.settings.capital}
        if not self.curve or self.curve[-1]["tick"] != self.engine.tick:
            self.curve.append(point)

    def step(self):
        if self.status not in {"running", "settling"}:
            return
        planned, self.pending = self.pending, []
        orders = [Order(d["symbol"], Side(d["side"]), d["qty"], d["price"], tid, ioc=True)
                  for tid, d in planned]
        self.engine.step(orders)
        for tid in (AI_ID, HOLD_ID):
            trades = self.engine.executions[tid]
            for trade in trades[self.last_seen[tid]:]:
                if trade["side"] == "BUY":
                    self.entry_ticks[tid].setdefault(trade["symbol"], trade["tick"])
                    self.spent[tid][trade["symbol"]] += trade["qty"] * trade["price"] + trade["fee"]
            self.last_seen[tid] = len(trades)
            for symbol in list(self.entry_ticks[tid]):
                if self.engine.by_id[tid].positions.get(symbol, 0) == 0:
                    del self.entry_ticks[tid][symbol]
        for tid, decision in planned:
            fills = [t for t in self.engine.executions[tid][self._prior_counts.get(tid, 0):]
                     if t["symbol"] == decision["symbol"] and t["side"] == decision["side"]]
            filled = sum(t["qty"] for t in fills)
            self.decisions.append({**decision, "trader": tid, "tick": self.engine.tick - 1,
                                   "execution_tick": self.engine.tick, "filled": filled,
                                   "avg_price": sum(t["qty"] * t["price"] for t in fills) / filled if filled else None})
        self._record_curve()
        if self.drawdowns[AI_ID] >= self.settings.max_drawdown:
            self.agent_halted = True
        if self.status == "running" and self.engine.tick >= HISTORY + self.settings.duration:
            self.finish()
        if self.status == "settling":
            if not any(q for tid in (AI_ID, HOLD_ID) for q in self.engine.by_id[tid].positions.values()):
                self.status = "completed"
                self.pending = []
                return
            if self.engine.tick - self.settle_started >= 100:
                self.status = "completed"  # report stranded inventory explicitly
                self.pending = []
                return
        self.model = self.predictor.step(self.engine)
        if self.status == "settling" or self.agent_halted or self.engine.tick % 5 == 0:
            self._plan(liquidate=self.status == "settling")

    def _plan(self, liquidate: bool):
        self.pending = []
        self._prior_counts = {tid: len(self.engine.executions[tid]) for tid in (AI_ID, HOLD_ID)}
        # Pass only public order-book observations into the policy.
        quotes = [{key: q[key] for key in ("symbol", "last", "bid", "ask", "depth")}
                  for q in self.engine.snapshot()["symbols"]]
        signals = (self.model or {}).get("signals", {})
        if (not signals or self.engine.tick < HISTORY) and not liquidate:
            return
        limits = {**asdict(self.settings), "fee_bps": self.engine.cfg.fee_bps}
        for tid in (AI_ID, HOLD_ID):
            account = self.engine.portfolio(tid)
            ages = {s: self.engine.tick - tick for s, tick in self.entry_ticks[tid].items()}
            planned = plan_orders(quotes, signals, account, limits, ages,
                                  self.predictor.horizon if self.predictor else 20,
                                  liquidate=liquidate or (tid == AI_ID and self.agent_halted),
                                  hold_benchmark=tid == HOLD_ID, spent=self.spent[tid])
            self.pending.extend((tid, d) for d in planned)
        if not self.pending and self.engine.tick % 20 == 0:
            self.decisions.append({"tick": self.engine.tick, "trader": AI_ID, "side": "WAIT",
                                   "symbol": "—", "qty": 0, "filled": 0, "price": None,
                                   "reason": "No executable opportunity exceeds the risk and cost limits"})

    def account(self, tid: str) -> dict:
        portfolio = self.engine.portfolio(tid)
        value = self._equity(tid)
        capital = self.settings.capital
        liquidation = self.engine.by_id[tid].cash
        missing = 0
        for pos in portfolio["positions"]:
            qty, proceeds = self.engine.books[pos["symbol"]].execution_quote(
                Order(pos["symbol"], Side.SELL, pos["shares"], None, tid))
            liquidation += proceeds * (1 - self.engine.cfg.fee_bps / 10_000)
            missing += pos["shares"] - qty
        return {**portfolio, "id": tid, "initial": capital, "net_pnl": round(value - capital, 2),
                "return_pct": (value / capital - 1) * 100, "max_drawdown_pct": self.drawdowns[tid] * 100,
                "exposure_pct": portfolio["equity"] / value * 100 if value > 0 else 0,
                "fills": len(self.engine.executions[tid]), "unrealized_pnl": round(sum(p["pnl"] for p in portfolio["positions"]), 2),
                "liquidation_value": round(liquidation, 2) if not missing else None,
                "illiquid_shares": missing}

    def population(self) -> list[dict]:
        grouped = defaultdict(list)
        for trader in self.engine.traders:
            if trader.id != "USER":
                grouped[trader.archetype].append(trader)
        result = []
        for name, traders in grouped.items():
            capital = sum(t.traits.capital for t in traders)
            value = sum(self._equity(t.id) for t in traders)
            result.append({"name": name, "count": len(traders), "capital": capital,
                           "return_pct": (value / capital - 1) * 100,
                           "fear": sum(t.fear for t in traders) / len(traders),
                           "greed": sum(t.greed for t in traders) / len(traders),
                           "buy_volume": sum(t.buy_notional for t in traders),
                           "sell_volume": sum(t.sell_notional for t in traders)})
        return sorted(result, key=lambda r: r["capital"], reverse=True)

    def snapshot(self) -> dict:
        agent, hold = self.account(AI_ID), self.account(HOLD_ID)
        stride = max(1, len(self.curve) // 400)
        curve = self.curve[::stride]
        if curve[-1] != self.curve[-1]:
            curve.append(self.curve[-1])
        closed = not agent["positions"]
        verdict = ("Profitable" if agent["net_pnl"] > 0 else "Loss" if agent["net_pnl"] < 0 else "Flat") if closed else "Open inventory"
        return {**self.engine.snapshot(), "model": self.model,
                "arena": {"id": self.id, "created_at": self.created_at, "status": self.status,
                          "error": self.error, "settings": asdict(self.settings), "agent_halted": self.agent_halted,
                          "elapsed": max(0, self.engine.tick - HISTORY), "warmup": HISTORY,
                          "verdict": verdict if self.terminal else "In progress",
                          "agent": agent, "benchmark": hold, "excess_pnl": round(agent["net_pnl"] - hold["net_pnl"], 2),
                          "curve": curve, "decisions": self.decisions[-40:][::-1],
                          "fills": self.engine.executions[AI_ID][-50:][::-1], "population": self.population(),
                          "manual_interventions": len(self.engine.executions["USER"]),
                          "model_fingerprint": getattr(self.predictor, "fingerprint", None),
                          "policy_version": 1, "sim_version": SIM_VERSION,
                          "model_ready": self.predictor is not None}}

    def result(self) -> dict:
        result = self.snapshot()
        result["arena"]["decisions"] = self.decisions
        result["arena"]["fills"] = self.engine.executions[AI_ID]
        result["arena"]["engine_config"] = asdict(self.engine.cfg)
        result["arena"]["manual_fills"] = self.engine.executions["USER"]
        return result


class RunStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, result TEXT NOT NULL)")

    def save(self, arena: Arena):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, ?)",
                       (arena.id, arena.created_at, json.dumps(arena.result(), allow_nan=False)))
        arena.archived = True

    def list(self) -> list[dict]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT result FROM runs ORDER BY created_at DESC LIMIT 30").fetchall()
        return [{k: a[k] for k in ("id", "created_at", "status", "settings", "elapsed", "verdict", "agent", "benchmark", "excess_pnl")}
                for (raw,) in rows for a in [json.loads(raw)["arena"]]]

    def get(self, run_id: str) -> dict | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT result FROM runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None
