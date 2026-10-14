"""Unit tests for Tier 1 JevClient, OpenRouter fallback, DiskCache, and MockJevClient (Task 3.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from engine.clients.jev_client import (
    JevClient,
    MockJevClient,
    compute_cache_key,
    passes_jev_threshold,
)
from engine.models.schemas import (
    AlignmentChoice,
    CandidateReintroduction,
    JevEvaluationResult,
)


class _DummyResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._json_data


class _RecordingSession:
    def __init__(self, response_payload: dict[str, Any]) -> None:
        self.response_payload = response_payload
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _DummyResponse:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers or {},
                "timeout": timeout,
            }
        )
        return _DummyResponse(self.response_payload)


@pytest.fixture()
def sample_candidate() -> CandidateReintroduction:
    return CandidateReintroduction(
        entity_slug="high-marshal-vasquez",
        canonical_name="Vasquez",
        current_chapter_index=3,
        current_chapter_title="Chapter Four: The Battle of Red Ridge",
        current_paragraph_index=1,
        current_scene_text=(
            "High Marshal Vasquez charged into the breach at the head of five "
            "hundred armored cataphracts."
        ),
        last_seen_chapter_index=0,
        pages_absent=45,
        prior_excerpts=[
            "High Marshal Vasquez stood atop the north bastion, his scarred iron gauntlets resting upon the battlements.",
            '"Hold the line at all costs," Vasquez ordered, his voice cutting through the rising thunder of artillery.',
        ],
    )


# ── MockJevClient & Thresholds ────────────────────────────


def test_mock_jev_client_deterministic(
    sample_candidate: CandidateReintroduction,
) -> None:
    mock_client = MockJevClient()
    res = mock_client.evaluate_candidate(sample_candidate)

    assert isinstance(res, JevEvaluationResult)
    assert res.entity_slug == "high-marshal-vasquez"
    assert res.chapter_index == 3
    assert res.is_significant_reintroduction == 0.88
    assert res.requires_context_refresher == 4
    assert res.current_alignment is AlignmentChoice.ALLY
    assert res.provider_used == "mock"
    assert res.cached is False
    assert mock_client.call_count == 1
    assert passes_jev_threshold(res) is True


def test_mock_jev_client_overrides(
    sample_candidate: CandidateReintroduction,
) -> None:
    mock_client = MockJevClient(
        overrides={
            "high-marshal-vasquez": {
                "is_significant_reintroduction": 0.25,
                "requires_context_refresher": 1,
                "current_alignment": "ambiguous",
            }
        }
    )
    res = mock_client.evaluate_candidate(sample_candidate)
    assert res.is_significant_reintroduction == 0.25
    assert res.requires_context_refresher == 1
    assert res.current_alignment is AlignmentChoice.AMBIGUOUS
    assert passes_jev_threshold(res) is False


def test_passes_jev_threshold_or_logic() -> None:
    high_prob_only = JevEvaluationResult(
        entity_slug="a",
        chapter_index=1,
        is_significant_reintroduction=0.72,
        requires_context_refresher=1,
        current_alignment=AlignmentChoice.NEUTRAL,
        provider_used="mock",
    )
    high_score_only = JevEvaluationResult(
        entity_slug="b",
        chapter_index=1,
        is_significant_reintroduction=0.30,
        requires_context_refresher=3,
        current_alignment=AlignmentChoice.NEUTRAL,
        provider_used="mock",
    )
    neither = JevEvaluationResult(
        entity_slug="c",
        chapter_index=1,
        is_significant_reintroduction=0.69,
        requires_context_refresher=2,
        current_alignment=AlignmentChoice.NEUTRAL,
        provider_used="mock",
    )
    assert passes_jev_threshold(high_prob_only) is True
    assert passes_jev_threshold(high_score_only) is True
    assert passes_jev_threshold(neither) is False


# ── OpenRouter Dev Fallback Mode ──────────────────────────


def test_openrouter_fallback_payload_and_parsing(
    sample_candidate: CandidateReintroduction,
    tmp_path: Path,
) -> None:
    or_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "is_significant_reintroduction": 0.91,
                            "requires_context_refresher": 5,
                            "current_alignment": "ally",
                        }
                    )
                }
            }
        ]
    }
    session = _RecordingSession(or_response)
    client = JevClient(
        provider_mode="openrouter_fallback",
        openrouter_api_key="or-test-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="google/gemini-2.0-flash-exp:free",
        cache_dir=tmp_path / "cache",
        request_delay=0.0,
        session=session,  # type: ignore[arg-type]
    )
    try:
        result = client.evaluate_candidate(sample_candidate)
    finally:
        client.close()

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer or-test-key"

    sent_payload = call["json"]
    assert sent_payload["model"] == "google/gemini-2.0-flash-exp:free"
    assert sent_payload["response_format"] == {"type": "json_object"}
    user_msg = json.loads(sent_payload["messages"][1]["content"])
    assert user_msg["entity_slug"] == "high-marshal-vasquez"
    assert user_msg["pages_absent"] == 45
    assert len(user_msg["prior_excerpts"]) == 2

    assert result.provider_used == "openrouter_fallback"
    assert result.is_significant_reintroduction == 0.91
    assert result.requires_context_refresher == 5
    assert result.current_alignment is AlignmentChoice.ALLY
    assert result.cached is False


def test_missing_jev_key_forces_openrouter_fallback_in_client(
    tmp_path: Path,
) -> None:
    client = JevClient(
        provider_mode="jev",
        jev_api_key="",
        openrouter_api_key="or-key",
        cache_dir=tmp_path / "cache",
        request_delay=0.0,
    )
    try:
        assert client.provider_mode == "openrouter_fallback"
    finally:
        client.close()


# ── Native TypeSafe Jev Mode ──────────────────────────────


def test_jev_native_payload_and_parsing(
    sample_candidate: CandidateReintroduction,
    tmp_path: Path,
) -> None:
    jev_response = {
        "answers": {
            "is_significant_reintroduction": 0.84,
            "requires_context_refresher": 4,
            "current_alignment": "ally",
        }
    }
    session = _RecordingSession(jev_response)
    client = JevClient(
        provider_mode="jev",
        jev_api_key="jev-live-key",
        jev_base_url="https://api.typesafe.ai",
        cache_dir=tmp_path / "cache",
        request_delay=0.0,
        session=session,  # type: ignore[arg-type]
    )
    try:
        result = client.evaluate_candidate(sample_candidate)
    finally:
        client.close()

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "https://api.typesafe.ai/v1/evaluate"
    assert call["headers"]["Authorization"] == "Bearer jev-live-key"

    payload = call["json"]
    assert payload["state"]["entity_slug"] == "high-marshal-vasquez"
    assert payload["state"]["pages_absent"] == 45
    questions = payload["questions"]
    assert questions["is_significant_reintroduction"]["type"] == "noul"
    assert questions["requires_context_refresher"]["type"] == "score"
    assert questions["requires_context_refresher"]["range"] == [0, 5]
    assert questions["current_alignment"]["type"] == "choice"
    assert set(questions["current_alignment"]["choices"]) == {
        "ally",
        "adversary",
        "neutral",
        "ambiguous",
    }

    assert result.provider_used == "jev_native"
    assert result.is_significant_reintroduction == 0.84
    assert result.requires_context_refresher == 4
    assert result.current_alignment is AlignmentChoice.ALLY
    assert result.cached is False


# ── Deterministic DiskCache Hits & Force Refresh ──────────


def test_diskcache_hit_and_force_eval_bypass(
    sample_candidate: CandidateReintroduction,
    tmp_path: Path,
) -> None:
    jev_response = {
        "answers": {
            "is_significant_reintroduction": 0.77,
            "requires_context_refresher": 3,
            "current_alignment": "neutral",
        }
    }
    session = _RecordingSession(jev_response)
    cache_dir = tmp_path / "jev_cache"

    client = JevClient(
        provider_mode="jev",
        jev_api_key="jev-key",
        cache_dir=cache_dir,
        request_delay=0.0,
        session=session,  # type: ignore[arg-type]
    )
    try:
        first = client.evaluate_candidate(sample_candidate)
        assert first.cached is False
        assert len(session.calls) == 1

        # Second call with identical candidate must hit diskcache without HTTP call
        second = client.evaluate_candidate(sample_candidate)
        assert second.cached is True
        assert second.is_significant_reintroduction == 0.77
        assert second.requires_context_refresher == 3
        assert second.current_alignment is AlignmentChoice.NEUTRAL
        assert len(session.calls) == 1

        # Third call with force_eval=True must bypass cache and issue a new HTTP call
        third = client.evaluate_candidate(sample_candidate, force_eval=True)
        assert third.cached is False
        assert len(session.calls) == 2
    finally:
        client.close()


def test_compute_cache_key_determinism(
    sample_candidate: CandidateReintroduction,
) -> None:
    key1 = compute_cache_key(sample_candidate)
    key2 = compute_cache_key(sample_candidate.model_copy(deep=True))
    modified = sample_candidate.model_copy(update={"current_chapter_index": 4})
    key3 = compute_cache_key(modified)

    assert len(key1) == 64
    assert key1 == key2
    assert key1 != key3
