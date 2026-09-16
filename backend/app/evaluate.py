"""Run funded agents on fresh simulated markets; archive every outcome, including losses."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from math import comb
from pathlib import Path
from statistics import mean

import numpy as np

from .arena import Arena, Experiment, RunStore
from ml.predict import Predictor

FINAL_SEEDS = range(501, 509)
GRID = {'min_probability': (.55, .62, .70), 'min_edge_bps': (0, 20, 50), 'max_position': (.10, .20, .30)}
DRAWDOWN_PENALTY = 0.5


def excess_pct(r: dict) -> float:
    return r['excess_pnl'] / r['settings']['capital'] * 100


def seed_bootstrap(rows: list[dict], value, draws: int = 10_000, seed: int = 0) -> dict:
    """Percentile CI for the pooled mean, resampling whole seeds because scenarios share a seed."""
    groups = {}
    for r in rows:
        groups.setdefault(r['settings']['seed'], []).append(value(r))
    sums = np.array([sum(g) for g in groups.values()])
    counts = np.array([len(g) for g in groups.values()])
    picks = np.random.default_rng(seed).integers(len(sums), size=(draws, len(sums)))
    low, high = np.percentile(sums[picks].sum(1) / counts[picks].sum(1), [2.5, 97.5])
    return {'mean': float(sums.sum() / counts.sum()), 'ci95': [float(low), float(high)],
            'seeds': len(sums), 'runs': len(rows), 'draws': draws, 'bootstrap_seed': seed}


def sign_test(values: list[float]) -> dict:
    positive, negative = sum(v > 0 for v in values), sum(v < 0 for v in values)
    n = positive + negative
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(positive, negative) + 1)) / 2 ** n) if n else 1.0
    return {'positive': positive, 'negative': negative, 'ties': len(values) - n, 'p_two_sided': p}


def summarize(results: list[dict], bootstrap_seed: int = 0) -> dict:
    agents = [r for r in results if not r['agent']['positions']]
    paired = [r for r in agents if not r['benchmark']['positions']]
    by_seed = {}
    for r in paired:
        by_seed.setdefault(r['settings']['seed'], []).append(excess_pct(r))
    return {'runs': len(results), 'agent_settled': len(agents), 'paired_settled': len(paired),
            'profitable': sum(r['agent']['net_pnl'] > 0 for r in agents),
            'losses': sum(r['agent']['net_pnl'] < 0 for r in agents),
            'flat': sum(r['agent']['net_pnl'] == 0 for r in agents),
            'agent_open_inventory_runs': len(results) - len(agents),
            'benchmark_open_inventory_runs': sum(bool(r['benchmark']['positions']) for r in results),
            'beat_hold': sum(r['excess_pnl'] > 0 for r in paired),
            'mean_return_pct': mean(r['agent']['return_pct'] for r in agents) if agents else None,
            'mean_excess_pnl': mean(r['excess_pnl'] for r in paired) if paired else None,
            'statistics': {
                'return_pct': seed_bootstrap(agents, lambda r: r['agent']['return_pct'], seed=bootstrap_seed) if agents else None,
                'excess_return_pct': seed_bootstrap(paired, excess_pct, seed=bootstrap_seed) if paired else None,
                'sign_test_runs': sign_test([excess_pct(r) for r in paired]),
                'sign_test_seed_means': sign_test([mean(v) for v in by_seed.values()])}}


def run_one(job: tuple) -> Arena:
    scenario, seed, ticks, capital, model, policy = job
    arena = Arena(Experiment(seed=seed, duration=ticks, capital=capital, scenario=scenario, **policy), Predictor(model))
    while not arena.terminal:
        arena.step()
    return arena


def row(arena: Arena) -> dict:
    result = arena.snapshot()['arena']
    return {k: result[k] for k in ['id', 'settings', 'status', 'verdict', 'agent', 'benchmark', 'excess_pnl',
                                   'model_fingerprint', 'sim_version', 'policy_version']}


def tune_one(job: tuple) -> dict:
    r = row(run_one(job))
    return {'scenario': job[0], 'seed': job[1], 'return_pct': r['agent']['return_pct'],
            'excess_pct': excess_pct(r), 'max_drawdown_pct': r['agent']['max_drawdown_pct'],
            'agent_open': bool(r['agent']['positions']), 'benchmark_open': bool(r['benchmark']['positions']),
            'model_fingerprint': r['model_fingerprint']}


def tune(args) -> dict:
    """Grid sweep on tuning seeds; score = mean excess return - penalty * mean Atlas drawdown (all runs, marked)."""
    if set(args.seeds) & set(FINAL_SEEDS):
        raise ValueError('final seeds 501-508 must never be used for policy selection')
    configs = [dict(zip(GRID, values)) for values in product(*GRID.values())]
    jobs = [(s, seed, args.ticks, args.capital, args.model, c) for c in configs for s in args.scenarios for seed in args.seeds]
    with ProcessPoolExecutor(args.workers) as pool:
        runs = list(pool.map(tune_one, jobs, chunksize=4))
    per = len(args.scenarios) * len(args.seeds)
    table = []
    for i, config in enumerate(configs):
        chunk = runs[i * per:(i + 1) * per]
        excess, drawdown = mean(r['excess_pct'] for r in chunk), mean(r['max_drawdown_pct'] for r in chunk)
        table.append({**config, 'mean_return_pct': mean(r['return_pct'] for r in chunk), 'mean_excess_pct': excess,
                      'mean_drawdown_pct': drawdown, 'score': excess - DRAWDOWN_PENALTY * drawdown,
                      'agent_open_runs': sum(r['agent_open'] for r in chunk), 'runs': chunk})
    best = max(table, key=lambda t: t['score'])
    return {'method': tune.__doc__, 'drawdown_penalty': DRAWDOWN_PENALTY, 'grid': GRID, 'seeds': args.seeds,
            'scenarios': args.scenarios, 'ticks': args.ticks, 'chosen': {k: best[k] for k in GRID},
            'ranking': sorted(table, key=lambda t: -t['score'])}


def markdown(output: dict) -> str:
    s, st = output['summary'], output['summary']['statistics']
    ci = lambda b: f"{b['mean']:+.2f}% (95% CI {b['ci95'][0]:+.2f}% to {b['ci95'][1]:+.2f}%)" if b else '—'
    sign = lambda t: f"{t['positive']} positive, {t['negative']} negative, {t['ties']} ties; two-sided p = {t['p_two_sided']:.3f}"
    lines = [f"**{s['runs']} runs: {s['profitable']} profitable, {s['losses']} losing, {s['flat']} flat Atlas accounts "
             f"({s['agent_settled']} fully liquidated).** Atlas beat buy-and-hold in {s['beat_hold']} of "
             f"{s['paired_settled']} fully liquidated paired comparisons.", "",
             "| Statistic | Value |", "|---|---|",
             f"| Mean Atlas return | {ci(st['return_pct'])} |",
             f"| Mean Atlas minus buy-and-hold return | {ci(st['excess_return_pct'])} |",
             f"| Sign test on excess, per run | {sign(st['sign_test_runs'])} |",
             f"| Sign test on excess, per-seed means | {sign(st['sign_test_seed_means'])} |", "",
             "Bootstrap: 10,000 draws resampling whole seeds (scenarios within a seed are dependent), "
             f"fixed bootstrap seed {st['return_pct']['bootstrap_seed'] if st['return_pct'] else 0}. "
             "The per-run sign test treats dependent scenarios as independent; the per-seed test does not.", "",
             "| Scenario | Seed | Atlas P&L | Buy & hold P&L | Excess return | Atlas drawdown | Benchmark inventory |",
             "|---|---:|---:|---:|---:|---:|---|"]
    lines += [f"| {r['settings']['scenario'].title()} | {r['settings']['seed']} | {r['agent']['net_pnl']:+,.2f} | "
              f"{r['benchmark']['net_pnl']:+,.2f} | {excess_pct(r):+.2f}% | {r['agent']['max_drawdown_pct']:.2f}% | "
              f"{'Open, marked value' if r['benchmark']['positions'] else 'Closed'} |" for r in output['runs']]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', nargs='+', type=int, default=[101, 102, 103])
    parser.add_argument('--ticks', type=int, default=1500)
    parser.add_argument('--capital', type=float, default=100_000)
    parser.add_argument('--scenarios', nargs='+', choices=['balanced', 'volatile', 'retail'], default=['balanced'])
    parser.add_argument('--model', default='ml/model.pkl')
    parser.add_argument('--database', default='data/runs.sqlite3')
    parser.add_argument('--out', default='reports/agent-evaluation.json')
    parser.add_argument('--markdown', default='')
    parser.add_argument('--bootstrap-seed', type=int, default=0)
    parser.add_argument('--policy', default='', help='JSON object of Experiment policy overrides')
    parser.add_argument('--tune', action='store_true')
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if args.tune:
        output = tune(args)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'chosen': output['chosen'], 'top': [{k: v for k, v in t.items() if k != 'runs'}
                                                              for t in output['ranking'][:5]]}, indent=2), flush=True)
        return
    policy = json.loads(args.policy) if args.policy else {}
    store = RunStore(Path(args.database))
    results = []
    for scenario in args.scenarios:
        for seed in args.seeds:
            arena = run_one((scenario, seed, args.ticks, args.capital, args.model, policy))
            store.save(arena)
            results.append(row(arena))
            r = results[-1]
            print(f"{scenario:9s} seed {seed:4d}: Atlas {r['agent']['net_pnl']:+9.2f}, "
                  f"hold {r['benchmark']['net_pnl']:+9.2f}, drawdown {r['agent']['max_drawdown_pct']:.2f}%, "
                  f"{r['verdict']}", flush=True)
    summary = summarize(results, args.bootstrap_seed)
    output = {'method': 'Funded accounts, shared live matching engine, next-tick orders, fees and finite liquidity. Synthetic markets only.',
              'summary': summary, 'runs': results}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    if args.markdown:
        Path(args.markdown).write_text(markdown(output) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
