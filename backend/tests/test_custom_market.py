"""Custom market settings must be validated, applied, and saved."""
import pytest
from pydantic import ValidationError

from app.api.routes import RunIn
from app.arena import Arena, Experiment, RunStore
from app.config import Config


MARKET = dict(news_prob=.25, news_notional=150_000, stress_enter_prob=.02, retail_multiplier=2.0)


def test_custom_market_changes_simulation_and_archives_settings(tmp_path):
    settings = Experiment(**RunIn(scenario="custom", market=MARKET, duration=2750).model_dump())
    arena = Arena(settings, None)
    cfg = arena.engine.cfg
    assert (cfg.news_prob, cfg.news_notional, cfg.stress_enter_prob) == (.25, 150_000, .02)
    for name in ("fomo", "weak_hands", "retail"):
        assert cfg.mix[name] == pytest.approx(Config().mix[name] * 2)
    assert cfg.mix["institution"] == Config().mix["institution"]
    store = RunStore(tmp_path / "runs.db")
    store.save(arena)
    assert store.get(arena.id)["arena"]["settings"]["market"] == MARKET
    assert store.page(scenario="custom")["total"] == 1
    assert settings.duration == 2750


def test_presets_stay_unchanged_and_reject_overrides():
    default = Config()
    balanced = Arena(Experiment(), None).engine.cfg
    assert (balanced.news_prob, balanced.news_notional, balanced.stress_enter_prob, balanced.mix) == (
        default.news_prob, default.news_notional, default.stress_enter_prob, default.mix)
    assert Arena(Experiment(scenario="volatile"), None).engine.cfg.news_prob == .25
    assert Arena(Experiment(scenario="retail"), None).engine.cfg.mix["fomo"] == .40
    with pytest.raises(ValueError):
        Experiment(scenario="balanced", market=MARKET)
    with pytest.raises(ValidationError):
        RunIn(scenario="balanced", market=MARKET)


def test_custom_market_rejects_missing_extra_invalid_and_nonfinite_values():
    with pytest.raises(ValidationError):
        RunIn(scenario="custom")
    for name, value in [("news_prob", .51), ("news_notional", 9999),
                        ("stress_enter_prob", float("nan")), ("retail_multiplier", True)]:
        invalid = {**MARKET, name: value}
        with pytest.raises(ValidationError):
            RunIn(scenario="custom", market=invalid)
        with pytest.raises(ValueError):
            Experiment(scenario="custom", market=invalid)
    with pytest.raises(ValidationError):
        RunIn(scenario="custom", market={**MARKET, "unknown": 1})
    with pytest.raises(ValueError):
        Experiment(scenario="custom", market={k: v for k, v in MARKET.items() if k != "news_prob"})
    for duration in (99, 10001, 150.5):
        with pytest.raises(ValidationError):
            RunIn(duration=duration)
    assert RunIn(duration=100).duration == 100
    assert RunIn(duration=10000).duration == 10000
