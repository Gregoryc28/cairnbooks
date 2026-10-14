"""Tests for engine.config (Task 1.1)."""

import importlib

from engine import config


def test_data_directories_exist() -> None:
    for path in (config.JOBS_DIR, config.OUTPUTS_DIR, config.JEV_CACHE_DIR):
        assert path.exists() and path.is_dir()
        assert path.parent == config.DATA_DIR


def test_default_thresholds(monkeypatch) -> None:
    for name in (
        "JEV_REINTRO_PROB_THRESHOLD",
        "JEV_REFRESHER_SCORE_MIN",
        "DEFAULT_MIN_PAGE_GAP",
        "MAX_SYNOPSIS_WORDS",
    ):
        monkeypatch.setenv(name, "")
    reloaded = importlib.reload(config)
    assert reloaded.JEV_REINTRO_PROB_THRESHOLD == 0.70
    assert reloaded.JEV_REFRESHER_SCORE_MIN == 3
    assert reloaded.DEFAULT_MIN_PAGE_GAP == 30
    assert reloaded.MAX_SYNOPSIS_WORDS == 15


def test_missing_jev_key_forces_openrouter_fallback(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER_MODE", "jev")
    monkeypatch.setenv("JEV_API_KEY", "")
    reloaded = importlib.reload(config)
    assert reloaded.AI_PROVIDER_MODE == "openrouter_fallback"


def test_jev_mode_with_key(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER_MODE", "jev")
    monkeypatch.setenv("JEV_API_KEY", "dummy-test-key")
    reloaded = importlib.reload(config)
    assert reloaded.AI_PROVIDER_MODE == "jev"
