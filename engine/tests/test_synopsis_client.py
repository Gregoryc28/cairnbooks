"""Unit tests for Tier 2 SynopsisClient and MockSynopsisClient (Task 3.2)."""

from __future__ import annotations

import json
from typing import Any

import requests  # type: ignore[import-untyped]

from engine.clients.synopsis_client import (
    MockSynopsisClient,
    SynopsisClient,
    build_fallback_synopsis,
    enforce_word_limit,
)
from engine.config import MAX_SYNOPSIS_WORDS


class _DummyResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._json_data


class _RecordingSession:
    def __init__(
        self,
        response_payload: dict[str, Any] | None = None,
        status_code: int = 200,
        raise_exc: Exception | None = None,
    ) -> None:
        self.response_payload = response_payload or {}
        self.status_code = status_code
        self.raise_exc = raise_exc
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
        if self.raise_exc is not None:
            raise self.raise_exc
        return _DummyResponse(self.response_payload, status_code=self.status_code)


# ── Word Count Enforcement ────────────────────────────────


def test_enforce_word_limit_short_text_unchanged() -> None:
    short = '"Commander of the Oakhaven garrison who defended the northern bastion."'
    result = enforce_word_limit(short, max_words=15)
    assert result == (
        "Commander of the Oakhaven garrison who defended the northern bastion."
    )
    assert len(result.split()) == 10
    assert len(result.split()) <= MAX_SYNOPSIS_WORDS


def test_enforce_word_limit_truncates_over_15_words() -> None:
    verbose = (
        "High Marshal Vasquez is the veteran commander of the Oakhaven "
        "garrison who stood atop the north bastion in Chapter One and "
        "ordered the archers to hold the line at all costs."
    )
    assert len(verbose.split()) > 15
    result = enforce_word_limit(verbose, max_words=15)
    words = result.split()
    assert len(words) == 15
    assert result.endswith("...")


def test_fallback_synopsis_strictly_within_15_words() -> None:
    prior = [
        (
            "High Marshal Vasquez stood atop the north bastion, his scarred iron "
            "gauntlets resting upon the battlements."
        ),
        (
            '"Hold the line at all costs," Vasquez ordered, his voice cutting '
            "through the rising thunder of artillery."
        ),
    ]
    synopsis = build_fallback_synopsis(
        entity_name="Vasquez",
        prior_excerpts=prior,
        last_seen_chapter=0,
        pages_absent=45,
    )
    assert synopsis.startswith("Vasquez (Ch. 1, 45p ago):")
    assert 1 <= len(synopsis.split()) <= MAX_SYNOPSIS_WORDS


# ── Zero-Spoiler Prompt Construction & API Parsing ────────


def test_zero_spoiler_prompt_and_api_success() -> None:
    api_payload = {
        "choices": [
            {
                "message": {
                    "content": (
                        "Oakhaven bastion commander who ordered troops to hold "
                        "the line against siege artillery."
                    )
                }
            }
        ]
    }
    session = _RecordingSession(response_payload=api_payload)
    client = SynopsisClient(
        api_key="or-test-key",
        base_url="https://openrouter.ai/api/v1",
        model="google/gemini-2.0-flash-exp:free",
        session=session,  # type: ignore[arg-type]
    )

    prior_excerpts = [
        "High Marshal Vasquez stood atop the north bastion.",
        '"Hold the line at all costs," Vasquez ordered.',
    ]
    synopsis = client.generate_synopsis(
        entity_name="Vasquez",
        prior_excerpts=prior_excerpts,
        last_seen_chapter=0,
        pages_absent=45,
    )

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer or-test-key"

    sent_json = call["json"]
    assert sent_json["model"] == "google/gemini-2.0-flash-exp:free"
    user_data = json.loads(sent_json["messages"][1]["content"])

    # Verify strictly prior excerpts and zero future chapter leakage
    assert user_data["entity_name"] == "Vasquez"
    assert user_data["last_seen_chapter"] == 1
    assert user_data["pages_absent"] == 45
    assert user_data["prior_excerpts"] == prior_excerpts
    assert "current_scene_text" not in user_data
    assert "Red Ridge" not in json.dumps(sent_json)
    assert "Chancellor Dennis" not in json.dumps(sent_json)

    assert len(synopsis.split()) <= MAX_SYNOPSIS_WORDS
    assert "Oakhaven bastion commander" in synopsis


def test_api_response_over_15_words_is_clamped() -> None:
    long_response = {
        "choices": [
            {
                "message": {
                    "content": (
                        "High Marshal Vasquez is a seasoned military leader who "
                        "commanded the defense of Oakhaven atop the northern "
                        "bastion during the opening artillery siege."
                    )
                }
            }
        ]
    }
    session = _RecordingSession(response_payload=long_response)
    client = SynopsisClient(
        api_key="or-test-key",
        session=session,  # type: ignore[arg-type]
    )
    synopsis = client.generate_synopsis(
        entity_name="Vasquez",
        prior_excerpts=["High Marshal Vasquez stood atop the north bastion."],
        last_seen_chapter=0,
        pages_absent=35,
    )
    assert len(synopsis.split()) == 15
    assert synopsis.endswith("...")


# ── Unreachable API & Missing Key Fallbacks ───────────────


def test_fallback_when_api_unreachable() -> None:
    session = _RecordingSession(
        raise_exc=requests.ConnectionError("OpenRouter unreachable")
    )
    client = SynopsisClient(
        api_key="or-test-key",
        session=session,  # type: ignore[arg-type]
    )
    synopsis = client.generate_synopsis(
        entity_name="Vasquez",
        prior_excerpts=["High Marshal Vasquez stood atop the north bastion."],
        last_seen_chapter=0,
        pages_absent=40,
    )
    assert len(session.calls) == 1
    assert synopsis.startswith("Vasquez (Ch. 1, 40p ago):")
    assert len(synopsis.split()) <= MAX_SYNOPSIS_WORDS


def test_fallback_when_api_key_missing() -> None:
    session = _RecordingSession()
    client = SynopsisClient(
        api_key="",
        session=session,  # type: ignore[arg-type]
    )
    synopsis = client.generate_synopsis(
        entity_name="Thorne",
        prior_excerpts=["Commander Thorne surveyed the advancing legion."],
        last_seen_chapter=0,
        pages_absent=30,
    )
    assert len(session.calls) == 0
    assert synopsis.startswith("Thorne (Ch. 1, 30p ago):")
    assert len(synopsis.split()) <= MAX_SYNOPSIS_WORDS


# ── MockSynopsisClient ────────────────────────────────────


def test_mock_synopsis_client_deterministic_and_overrides() -> None:
    mock_client = MockSynopsisClient(
        overrides={
            "Vasquez": (
                "Veteran High Marshal who commanded Oakhaven's northern bastion "
                "defense during the opening siege."
            )
        }
    )
    res_override = mock_client.generate_synopsis(
        entity_name="Vasquez",
        prior_excerpts=["High Marshal Vasquez stood atop the north bastion."],
        last_seen_chapter=0,
        pages_absent=45,
    )
    res_default = mock_client.generate_synopsis(
        entity_name="Jennifer",
        prior_excerpts=["Scout Jennifer trudged through grey dunes."],
        last_seen_chapter=1,
        pages_absent=32,
    )

    assert mock_client.call_count == 2
    assert len(res_override.split()) <= MAX_SYNOPSIS_WORDS
    assert "Veteran High Marshal" in res_override
    assert res_default.startswith("Jennifer (Ch. 2, 32p ago):")
    assert len(res_default.split()) <= MAX_SYNOPSIS_WORDS
