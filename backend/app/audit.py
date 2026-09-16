"""Falsification controls and price-dynamics diagnostics; never tune to a target win rate."""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import json
from pathlib import Path

import numpy as np

from .arena import AI_ID, Arena, Experiment
from .config import SIM_VERSION
from ml.predict import Predictor


class ControlPredictor:
    horizon = 20

    def __init__(self, kind: str, seed: int):
        self.kind = kind
        self.fingerprint = 'control:' + kind
        self.rng = np.random.default_rng(seed + 1_000_000)
        self.prices = defaultdict(lambda: deque(maxlen=21))

    def step(self, engine):
        signals = {}
        for symbol in engine.symbols:
            last = engine.last[symbol]
            history = self.prices[symbol]
            history.append(last)
            if self.kind == 'momentum':
                ret = last / history[0] - 1
            elif self.kind == 'random':
                ret = .03 if self.rng.random() < .5 else -.03
            else:
                ret = .03
            signals[symbol] = dict(price=last * (1 + ret), prob=.9 if ret > 0 else .1,
                                   return_pct=ret * 100)
        return {'signals': signals}


def correlation(x, y):
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def dynamics(prices: list[float]) -> dict:
    logp = np.log(prices)
    returns = np.diff(logp)
    variance = float(np.var(returns))
    forward = logp[20:] - logp[:-20]
    preceding = logp[20:-20] - logp[:-40]
    following = logp[40:] - logp[20:-20]
    return dict(return_acf1=correlation(returns[:-1], returns[1:]),
                absolute_return_acf1=correlation(np.abs(returns[:-1]), np.abs(returns[1:])),
                variance_ratio20=float(np.var(forward) / (20 * variance)) if variance else None,
                momentum_direction_accuracy=float(np.mean((preceding > 0) == (following > 0))),
                zero_return_fraction=float(np.mean(returns == 0)),
                excess_kurtosis=float(np.mean((returns - returns.mean()) ** 4) / variance ** 2 - 3) if variance else None)


def round_trips(fills: list[dict]) -> dict:
    inventory = defaultdict(lambda: [0, 0., 0.])
    closed = []
    for f in fills:
        pos = inventory[f['symbol']]
        qty, value = f['qty'], f['qty'] * f['price']
        if f['side'] == 'BUY':
            pos[0] += qty
            pos[1] += value + f['fee']
        else:
            cost = pos[1] * qty / pos[0]
            pos[0] -= qty
            pos[1] -= cost
            pos[2] += value - f['fee'] - cost
            if pos[0] == 0:
                closed.append(pos[2])
                pos[2] = 0.
    return dict(closed=len(closed), winners=sum(p > .005 for p in closed),
                losers=sum(p < -.005 for p in closed), net_pnl=sum(closed))


def run(seed: int, duration: int, strategy: str, model: str) -> dict:
    predictor = Predictor(model) if strategy == 'model' else ControlPredictor(strategy, seed)
    arena = Arena(Experiment(seed=seed, duration=duration), predictor)
    prices = defaultdict(list)
    while not arena.terminal:
        arena.step()
        if arena.engine.tick >= 60:
            for symbol, last in arena.engine.last.items():
                prices[symbol].append(last)
    account = arena.account(AI_ID)
    trips = round_trips(arena.engine.executions[AI_ID])
    if not account['positions']:
        assert abs(trips['net_pnl'] - account['net_pnl']) < .02
    makers = [t for t in arena.engine.traders if t.traits.is_market_maker]
    return dict(seed=seed, duration=duration, strategy=strategy, sim_version=SIM_VERSION,
                model=predictor.fingerprint, agent=account, round_trips=trips,
                benchmark=arena.account('HOLD'),
                model_accuracy=(arena.model or {}).get('accuracy'),
                dynamics={s: dynamics(p) for s, p in prices.items()},
                market_maker_pnl=sum(arena._equity(t.id) - t.traits.capital for t in makers))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', nargs='+', type=int, default=[301, 302, 303])
    parser.add_argument('--ticks', type=int, default=1500)
    parser.add_argument('--strategies', nargs='+', choices=['model', 'momentum', 'random', 'always_buy'],
                        default=['model', 'momentum', 'random', 'always_buy'])
    parser.add_argument('--model', default='ml/model.pkl')
    parser.add_argument('--out', default='reports/realism-audit.json')
    args = parser.parse_args()
    results = []
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    for strategy in args.strategies:
        for seed in args.seeds:
            row = run(seed, args.ticks, strategy, args.model)
            results.append(row)
            path.write_text(json.dumps(results, indent=2, allow_nan=False) + '\n')
            trips = row['round_trips']
            print(f"{strategy:10s} seed {seed}: {row['agent']['return_pct']:+.3f}%, "
                  f"{trips['winners']}/{trips['closed']} winning round trips, "
                  f"MM P&L {row['market_maker_pnl']:+,.0f}", flush=True)


if __name__ == '__main__':
    main()
