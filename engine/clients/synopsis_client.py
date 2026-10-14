"""Tier 2 Micro-LLM Synopsis Client for CairnBooks.

Synthesizes strictly spoiler-capped, <= 15-word context refresher footnotes
from prior chapter excerpts via OpenRouter (`OPENROUTER_SYNOPSIS_MODEL`),
with a deterministic local fallback template when the API is unreachable
and a `MockSynopsisClient` for `--test-mode`.
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests  # type: ignore[import-untyped]

from engine.config import (
    MAX_SYNOPSIS_WORDS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_SYNOPSIS_MODEL,
)

_WHITESPACE_RE = re.compile(r"\s+")
_SURROUNDING_QUOTES_RE = re.compile(r'^["\'\u201c\u2018`]+|["\'\u201d\u2019`]+$')
_TRAILING_PUNCT_RE = re.compile(r"[,:;—–\-]+$")


def enforce_word_limit(text: str, max_words: int = MAX_SYNOPSIS_WORDS) -> str:
    """Normalize whitespace and strictly cap ``text`` at ``max_words`` words."""
    cleaned = _WHITESPACE_RE.sub(" ", text.strip())
    cleaned = _SURROUNDING_QUOTES_RE.sub("", cleaned).strip()
    if not cleaned:
        return ""

    words = cleaned.split()
    if len(words) <= max_words:
        return " ".join(words)

    truncated = " ".join(words[:max_words])
    truncated = _TRAILING_PUNCT_RE.sub("", truncated).rstrip(".")
    return f"{truncated}..."


def build_fallback_synopsis(
    entity_name: str,
    prior_excerpts: list[str],
    last_seen_chapter: int,
    pages_absent: int,
    max_words: int = MAX_SYNOPSIS_WORDS,
) -> str:
    """Deterministic <= 15-word fallback template when the API is unavailable."""
    chapter_num = max(1, last_seen_chapter + 1)
    prefix = f"{entity_name} (Ch. {chapter_num}, {pages_absent}p ago):"

    if prior_excerpts and prior_excerpts[-1].strip():
        excerpt_words = _WHITESPACE_RE.sub(" ", prior_excerpts[-1].strip()).split()
        raw = f"{prefix} {' '.join(excerpt_words)}"
    else:
        raw = f"{prefix} Previously introduced in earlier chapters."

    return enforce_word_limit(raw, max_words=max_words)


class SynopsisClient:
    """Tier 2 OpenRouter client for <= 15-word spoiler-free footnote recaps."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = OPENROUTER_BASE_URL,
        model: str = OPENROUTER_SYNOPSIS_MODEL,
        max_words: int = MAX_SYNOPSIS_WORDS,
        session: requests.Session | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.api_key: str = OPENROUTER_API_KEY if api_key is None else api_key
        self.base_url: str = base_url.rstrip("/")
        self.model: str = model
        self.max_words: int = max(1, max_words)
        self.session: requests.Session = session or requests.Session()
        self.timeout: float = timeout

    def _endpoint(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def build_prompt_payload(
        self,
        entity_name: str,
        prior_excerpts: list[str],
        last_seen_chapter: int,
        pages_absent: int,
    ) -> dict[str, Any]:
        """Build a zero-spoiler OpenRouter chat payload from prior excerpts only."""
        system_prompt = (
            "You are a spoiler-free literary footnote assistant. "
            f"Write a concise context refresher of AT MOST {self.max_words} words "
            "reminding the reader who or what the entity is based ONLY on the "
            "provided prior excerpts. Do not speculate or invent facts. "
            "Return plain text only with no markdown or quotation marks."
        )
        user_payload = json.dumps(
            {
                "entity_name": entity_name,
                "last_seen_chapter": last_seen_chapter + 1,
                "pages_absent": pages_absent,
                "prior_excerpts": list(prior_excerpts),
                "max_words": self.max_words,
            },
            ensure_ascii=False,
        )
        return {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 60,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
        }

    def generate_synopsis(
        self,
        entity_name: str,
        prior_excerpts: list[str],
        last_seen_chapter: int,
        pages_absent: int,
    ) -> str:
        """Generate a <= 15-word synopsis, falling back deterministically on error."""
        if not self.api_key:
            return build_fallback_synopsis(
                entity_name=entity_name,
                prior_excerpts=prior_excerpts,
                last_seen_chapter=last_seen_chapter,
                pages_absent=pages_absent,
                max_words=self.max_words,
            )

        payload = self.build_prompt_payload(
            entity_name=entity_name,
            prior_excerpts=prior_excerpts,
            last_seen_chapter=last_seen_chapter,
            pages_absent=pages_absent,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self.session.post(
                self._endpoint(),
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
            raw_text = str(body["choices"][0]["message"]["content"]).strip()
            if not raw_text:
                raise ValueError("Empty synopsis content from OpenRouter")
            return enforce_word_limit(raw_text, max_words=self.max_words)
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ):
            return build_fallback_synopsis(
                entity_name=entity_name,
                prior_excerpts=prior_excerpts,
                last_seen_chapter=last_seen_chapter,
                pages_absent=pages_absent,
                max_words=self.max_words,
            )


class MockSynopsisClient:
    """Deterministic zero-API Tier 2 synopsis generator for ``--test-mode``."""

    def __init__(
        self,
        max_words: int = MAX_SYNOPSIS_WORDS,
        overrides: dict[str, str] | None = None,
    ) -> None:
        self.max_words: int = max(1, max_words)
        self.overrides: dict[str, str] = overrides or {}
        self.call_count: int = 0

    def generate_synopsis(
        self,
        entity_name: str,
        prior_excerpts: list[str],
        last_seen_chapter: int,
        pages_absent: int,
    ) -> str:
        self.call_count += 1
        if entity_name in self.overrides:
            return enforce_word_limit(
                self.overrides[entity_name], max_words=self.max_words
            )
        return build_fallback_synopsis(
            entity_name=entity_name,
            prior_excerpts=prior_excerpts,
            last_seen_chapter=last_seen_chapter,
            pages_absent=pages_absent,
            max_words=self.max_words,
        )
