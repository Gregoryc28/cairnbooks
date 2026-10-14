"""Tier 1 Discriminative Gatekeeper Client for CairnBooks.

Evaluates ``CandidateReintroduction`` instances against three typed primitives:
- ``is_significant_reintroduction`` (float in [0.0, 1.0], Jev ``noul``)
- ``requires_context_refresher`` (int in [0, 5], Jev ``score``)
- ``current_alignment`` (``AlignmentChoice``, Jev ``choice``)

Supports native TypeSafe Jev (``/v1/evaluate``), OpenRouter structured JSON
fallback, persistent SHA-256 caching via ``diskcache``, and a deterministic
``MockJevClient`` for ``--test-mode``.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

import diskcache  # type: ignore[import-untyped]
import requests  # type: ignore[import-untyped]

from engine.config import (
    AI_PROVIDER_MODE,
    CACHE_SCHEMA_VERSION,
    JEV_API_KEY,
    JEV_BASE_URL,
    JEV_CACHE_DIR,
    JEV_REFRESHER_SCORE_MIN,
    JEV_REINTRO_PROB_THRESHOLD,
    JEV_REQUEST_DELAY,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_FALLBACK_MODEL,
)
from engine.models.schemas import (
    AlignmentChoice,
    CandidateReintroduction,
    JevEvaluationResult,
)

_ALIGNMENT_VALUES: list[str] = [a.value for a in AlignmentChoice]
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.DOTALL)


def compute_cache_key(
    candidate: CandidateReintroduction,
    schema_version: str = CACHE_SCHEMA_VERSION,
) -> str:
    """Return deterministic SHA-256 cache key for a candidate evaluation."""
    payload = json.dumps(
        {
            "entity_slug": candidate.entity_slug,
            "chapter_index": candidate.current_chapter_index,
            "current_scene_text": candidate.current_scene_text,
            "schema_version": schema_version,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def passes_jev_threshold(
    result: JevEvaluationResult,
    prob_threshold: float = JEV_REINTRO_PROB_THRESHOLD,
    score_min: int = JEV_REFRESHER_SCORE_MIN,
) -> bool:
    """True when a Tier 1 evaluation qualifies for Tier 2 footnote synthesis."""
    return (
        result.is_significant_reintroduction >= prob_threshold
        or result.requires_context_refresher >= score_min
    )


def _clamp_prob(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return max(0.0, min(1.0, numeric))


def _clamp_score(value: Any) -> int:
    try:
        numeric = round(float(value))
    except (TypeError, ValueError):
        numeric = 0
    return max(0, min(5, numeric))


def _parse_alignment(value: Any) -> AlignmentChoice:
    if isinstance(value, AlignmentChoice):
        return value
    text = str(value).strip().lower()
    for choice in AlignmentChoice:
        if choice.value == text:
            return choice
    return AlignmentChoice.NEUTRAL


class JevClient:
    """Tier 1 evaluator with Jev native mode, OpenRouter fallback, and DiskCache."""

    def __init__(
        self,
        provider_mode: str | None = None,
        jev_api_key: str | None = None,
        openrouter_api_key: str | None = None,
        jev_base_url: str = JEV_BASE_URL,
        openrouter_base_url: str = OPENROUTER_BASE_URL,
        openrouter_model: str = OPENROUTER_FALLBACK_MODEL,
        cache_dir: Path = JEV_CACHE_DIR,
        request_delay: float = JEV_REQUEST_DELAY,
        session: requests.Session | None = None,
        timeout: float = 30.0,
    ) -> None:
        resolved_jev_key = JEV_API_KEY if jev_api_key is None else jev_api_key
        resolved_or_key = (
            OPENROUTER_API_KEY if openrouter_api_key is None else openrouter_api_key
        )
        requested_mode = (provider_mode or AI_PROVIDER_MODE).strip().lower()

        # Enforce AGENTS.md Invariant 2: fallback to OpenRouter if JEV_API_KEY is unset
        self.provider_mode: str = (
            "jev"
            if requested_mode == "jev" and bool(resolved_jev_key)
            else "openrouter_fallback"
        )
        self.jev_api_key: str = resolved_jev_key
        self.openrouter_api_key: str = resolved_or_key
        self.jev_base_url: str = jev_base_url.rstrip("/")
        self.openrouter_base_url: str = openrouter_base_url.rstrip("/")
        self.openrouter_model: str = openrouter_model
        self.request_delay: float = max(0.0, request_delay)
        self.timeout: float = timeout
        self.session: requests.Session = session or requests.Session()
        self.cache: diskcache.Cache = diskcache.Cache(str(cache_dir))

    def close(self) -> None:
        """Close the underlying diskcache handle."""
        self.cache.close()

    def build_jev_payload(self, candidate: CandidateReintroduction) -> dict[str, Any]:
        """Construct the native TypeSafe Jev ``/v1/evaluate`` request payload."""
        return {
            "state": {
                "entity_slug": candidate.entity_slug,
                "canonical_name": candidate.canonical_name,
                "current_chapter_index": candidate.current_chapter_index,
                "current_chapter_title": candidate.current_chapter_title,
                "last_seen_chapter_index": candidate.last_seen_chapter_index,
                "pages_absent": candidate.pages_absent,
                "prior_excerpts": list(candidate.prior_excerpts),
                "current_scene_text": candidate.current_scene_text,
            },
            "questions": {
                "is_significant_reintroduction": {
                    "type": "noul",
                    "prompt": (
                        f"Is {candidate.canonical_name}'s appearance in "
                        f"{candidate.current_chapter_title} after {candidate.pages_absent} "
                        "pages absent a narratively significant reintroduction?"
                    ),
                },
                "requires_context_refresher": {
                    "type": "score",
                    "range": [0, 5],
                    "prompt": (
                        f"From 0 to 5, how strongly would a reader benefit from a "
                        f"spoiler-free reminder about {candidate.canonical_name}?"
                    ),
                },
                "current_alignment": {
                    "type": "choice",
                    "choices": _ALIGNMENT_VALUES,
                    "prompt": (
                        f"Based solely on prior context, what is "
                        f"{candidate.canonical_name}'s alignment?"
                    ),
                },
            },
        }

    def build_openrouter_payload(
        self, candidate: CandidateReintroduction
    ) -> dict[str, Any]:
        """Construct the OpenRouter structured JSON fallback request payload."""
        system_prompt = (
            "You are a narrative memory evaluator for an e-reader compiler. "
            "Given an entity returning after an absence, respond ONLY with a valid "
            "JSON object containing exactly three keys:\n"
            '- "is_significant_reintroduction": float between 0.0 and 1.0\n'
            '- "requires_context_refresher": integer between 0 and 5\n'
            '- "current_alignment": one of ["ally", "adversary", "neutral", "ambiguous"]\n'
            "Use strictly the provided prior excerpts and current scene."
        )
        user_content = json.dumps(
            {
                "entity_slug": candidate.entity_slug,
                "canonical_name": candidate.canonical_name,
                "current_chapter_index": candidate.current_chapter_index,
                "current_chapter_title": candidate.current_chapter_title,
                "last_seen_chapter_index": candidate.last_seen_chapter_index,
                "pages_absent": candidate.pages_absent,
                "prior_excerpts": list(candidate.prior_excerpts),
                "current_scene_text": candidate.current_scene_text,
            },
            ensure_ascii=False,
        )
        return {
            "model": self.openrouter_model,
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }

    def evaluate_candidate(
        self,
        candidate: CandidateReintroduction,
        force_eval: bool = False,
    ) -> JevEvaluationResult:
        """Evaluate a candidate reintroduction with persistent disk caching."""
        cache_key = compute_cache_key(candidate)

        if not force_eval and cache_key in self.cache:
            cached_raw = self.cache[cache_key]
            cached_result = JevEvaluationResult.model_validate(cached_raw)
            return cached_result.model_copy(update={"cached": True})

        if self.request_delay > 0:
            time.sleep(self.request_delay)

        if self.provider_mode == "jev":
            result = self._call_jev_native(candidate)
        else:
            result = self._call_openrouter_fallback(candidate)

        self.cache[cache_key] = result.model_dump(mode="json")
        return result

    def _call_jev_native(
        self, candidate: CandidateReintroduction
    ) -> JevEvaluationResult:
        url = f"{self.jev_base_url}/v1/evaluate"
        headers = {
            "Authorization": f"Bearer {self.jev_api_key}",
            "Content-Type": "application/json",
        }
        payload = self.build_jev_payload(candidate)
        response = self.session.post(
            url, json=payload, headers=headers, timeout=self.timeout
        )
        response.raise_for_status()
        body = response.json()
        answers = body.get("answers", body.get("results", body))

        return JevEvaluationResult(
            entity_slug=candidate.entity_slug,
            chapter_index=candidate.current_chapter_index,
            is_significant_reintroduction=_clamp_prob(
                answers.get("is_significant_reintroduction", 0.0)
            ),
            requires_context_refresher=_clamp_score(
                answers.get("requires_context_refresher", 0)
            ),
            current_alignment=_parse_alignment(
                answers.get("current_alignment", AlignmentChoice.NEUTRAL.value)
            ),
            provider_used="jev_native",
            cached=False,
        )

    def _openrouter_endpoint(self) -> str:
        if self.openrouter_base_url.endswith("/v1"):
            return f"{self.openrouter_base_url}/chat/completions"
        return f"{self.openrouter_base_url}/v1/chat/completions"

    def _call_openrouter_fallback(
        self, candidate: CandidateReintroduction
    ) -> JevEvaluationResult:
        url = self._openrouter_endpoint()
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = self.build_openrouter_payload(candidate)
        response = self.session.post(
            url, json=payload, headers=headers, timeout=self.timeout
        )
        response.raise_for_status()
        body = response.json()

        raw_content = body["choices"][0]["message"]["content"]
        if isinstance(raw_content, str):
            cleaned = _JSON_FENCE_RE.sub("", raw_content.strip())
            parsed = json.loads(cleaned)
        elif isinstance(raw_content, dict):
            parsed = raw_content
        else:
            parsed = {}

        return JevEvaluationResult(
            entity_slug=candidate.entity_slug,
            chapter_index=candidate.current_chapter_index,
            is_significant_reintroduction=_clamp_prob(
                parsed.get("is_significant_reintroduction", 0.0)
            ),
            requires_context_refresher=_clamp_score(
                parsed.get("requires_context_refresher", 0)
            ),
            current_alignment=_parse_alignment(
                parsed.get("current_alignment", AlignmentChoice.NEUTRAL.value)
            ),
            provider_used="openrouter_fallback",
            cached=False,
        )


class MockJevClient:
    """Deterministic zero-API Tier 1 evaluator for ``--test-mode`` and unit tests."""

    def __init__(
        self,
        default_prob: float = 0.88,
        default_score: int = 4,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.default_prob = _clamp_prob(default_prob)
        self.default_score = _clamp_score(default_score)
        self.overrides: dict[str, dict[str, Any]] = overrides or {}
        self.call_count: int = 0

    @staticmethod
    def _infer_alignment(candidate: CandidateReintroduction) -> AlignmentChoice:
        prior_blob = " ".join(candidate.prior_excerpts).lower()
        name_lower = candidate.canonical_name.lower()
        if (
            any(
                token in name_lower or token in prior_blob
                for token in ("obsidian banner", "enemy", "betrayal")
            )
            and "marshal" not in prior_blob
            and "scout" not in prior_blob
        ):
            return AlignmentChoice.ADVERSARY
        if any(
            token in prior_blob
            for token in (
                "high marshal",
                "commander",
                "scout",
                "scholar",
                "hold the line",
                "bastion",
            )
        ):
            return AlignmentChoice.ALLY
        return AlignmentChoice.NEUTRAL

    def evaluate_candidate(
        self,
        candidate: CandidateReintroduction,
        force_eval: bool = False,
    ) -> JevEvaluationResult:
        _ = force_eval
        self.call_count += 1
        override = self.overrides.get(candidate.entity_slug, {})

        prob = _clamp_prob(
            override.get("is_significant_reintroduction", self.default_prob)
        )
        score = _clamp_score(
            override.get("requires_context_refresher", self.default_score)
        )
        alignment = _parse_alignment(
            override.get("current_alignment", self._infer_alignment(candidate))
        )

        return JevEvaluationResult(
            entity_slug=candidate.entity_slug,
            chapter_index=candidate.current_chapter_index,
            is_significant_reintroduction=prob,
            requires_context_refresher=score,
            current_alignment=alignment,
            provider_used="mock",
            cached=False,
        )
