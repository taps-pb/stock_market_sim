"""Seed-clustered bootstrap, sign test, and final-seed isolation in policy tuning."""
from types import SimpleNamespace

import pytest

from app.evaluate import seed_bootstrap, sign_test, summarize, tune


def run(seed, agent, hold, open_hold=False):
    account = lambda pnl, positions: dict(net_pnl=pnl, return_pct=pnl / 1000, positions=positions, max_drawdown_pct=1.)
    return dict(settings=dict(seed=seed, capital=100_000), agent=account(agent, []),
                benchmark=account(hold, ['X'] if open_hold else []), excess_pnl=agent - hold)


def test_bootstrap_resamples_whole_seeds_deterministically():
    rows = [run(1, 100, 0), run(1, 300, 0), run(2, -500, 0)]
    value = lambda r: r['agent']['return_pct']
    a, b = seed_bootstrap(rows, value, seed=3), seed_bootstrap(rows, value, seed=3)
    assert a == b and a['seeds'] == 2 and a['runs'] == 3
    assert a['mean'] == pytest.approx(-0.1 / 3)
    # Only two seed clusters exist: every resample mean is one of three pooled values.
    assert a['ci95'][0] == pytest.approx(-0.5) and a['ci95'][1] == pytest.approx(0.2)
    single = seed_bootstrap([run(7, 100, 0), run(7, -300, 0)], value)
    assert single['ci95'] == [pytest.approx(-0.1), pytest.approx(-0.1)]


def test_sign_test_and_summary_statistics():
    assert sign_test([1] * 8)['p_two_sided'] == pytest.approx(2 / 256)
    assert sign_test([1, -1, 0]) == dict(positive=1, negative=1, ties=1, p_two_sided=1.0)
    assert sign_test([])['p_two_sided'] == 1.0
    stats = summarize([run(1, 500, 0), run(1, 400, 100), run(2, -100, 200, open_hold=True)])['statistics']
    assert stats['excess_return_pct']['runs'] == 2  # open benchmark inventory is not a paired comparison
    assert stats['sign_test_seed_means']['positive'] == 1
    assert stats['return_pct']['seeds'] == 2


def test_tuning_refuses_final_seeds():
    with pytest.raises(ValueError, match='final seeds'):
        tune(SimpleNamespace(seeds=[601, 505], scenarios=['balanced'], ticks=100, capital=100_000, model='', workers=1))
