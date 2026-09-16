"""Run funded agents on fresh simulated markets; archive every outcome, including losses."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from .arena import Arena, Experiment, RunStore
from ml.predict import Predictor


def summarize(results: list[dict]) -> dict:
    agents = [r for r in results if not r['agent']['positions']]
    paired = [r for r in agents if not r['benchmark']['positions']]
    return {'runs': len(results), 'agent_settled': len(agents), 'paired_settled': len(paired),
            'profitable': sum(r['agent']['net_pnl'] > 0 for r in agents),
            'losses': sum(r['agent']['net_pnl'] < 0 for r in agents),
            'flat': sum(r['agent']['net_pnl'] == 0 for r in agents),
            'agent_open_inventory_runs': len(results) - len(agents),
            'benchmark_open_inventory_runs': sum(bool(r['benchmark']['positions']) for r in results),
            'beat_hold': sum(r['excess_pnl'] > 0 for r in paired),
            'mean_return_pct': mean(r['agent']['return_pct'] for r in agents) if agents else None,
            'mean_excess_pnl': mean(r['excess_pnl'] for r in paired) if paired else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', nargs='+', type=int, default=[101, 102, 103])
    parser.add_argument('--ticks', type=int, default=1500)
    parser.add_argument('--capital', type=float, default=100_000)
    parser.add_argument('--scenarios', nargs='+', choices=['balanced', 'volatile', 'retail'], default=['balanced'])
    parser.add_argument('--model', default='ml/model.pkl')
    parser.add_argument('--database', default='data/runs.sqlite3')
    parser.add_argument('--out', default='reports/agent-evaluation.json')
    args = parser.parse_args()
    store = RunStore(Path(args.database))
    results = []
    for scenario in args.scenarios:
        for seed in args.seeds:
            arena = Arena(Experiment(seed=seed, duration=args.ticks, capital=args.capital, scenario=scenario), Predictor(args.model))
            while not arena.terminal:
                arena.step()
            store.save(arena)
            result = arena.snapshot()['arena']
            row = {k: result[k] for k in ['id', 'settings', 'status', 'verdict', 'agent', 'benchmark', 'excess_pnl',
                                         'model_fingerprint', 'sim_version', 'policy_version']}
            results.append(row)
            print(f"{scenario:9s} seed {seed:4d}: Atlas {row['agent']['net_pnl']:+9.2f}, "
                  f"hold {row['benchmark']['net_pnl']:+9.2f}, drawdown {row['agent']['max_drawdown_pct']:.2f}%, "
                  f"{row['verdict']}", flush=True)
    summary = summarize(results)
    output = {'method': 'Funded accounts, shared live matching engine, next-tick orders, fees and finite liquidity. Synthetic markets only.',
              'summary': summary, 'runs': results}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
