"""Tests for engine.models.schemas (Task 1.2)."""

from typing import Any

import pytest
from pydantic import ValidationError

from engine.models.schemas import (
    AlignmentChoice,
    BakeJobState,
    CairnFootnote,
    CandidateReintroduction,
    EntityCategory,
    EntityMention,
    JevEvaluationResult,
    JobPhase,
    LoreEntity,
)


def _jev_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "entity_slug": "vasquez",
        "chapter_index": 3,
        "is_significant_reintroduction": 0.85,
        "requires_context_refresher": 4,
        "current_alignment": "ally",
        "provider_used": "mock",
    }
    base.update(overrides)
    return base


def _footnote_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "anchor_id": "cairn-vasquez-ch3",
        "entity_slug": "vasquez",
        "display_name": "Vasquez",
        "chapter_index": 3,
        "chapter_title": "Chapter Four",
        "paragraph_index": 2,
        "pages_absent": 42,
        "first_seen_chapter": 0,
        "last_seen_chapter": 0,
        "alignment": AlignmentChoice.ALLY,
        "jev_prob": 0.85,
        "jev_score": 4,
        "synopsis_text": "Fleet admiral who rescued the crew at Harrow Point.",
    }
    base.update(overrides)
    return base


# ── JevEvaluationResult bounds ────────────────────────────


@pytest.mark.parametrize("prob", [0.0, 0.5, 1.0])
def test_jev_prob_accepts_bounds(prob: float) -> None:
    result = JevEvaluationResult(**_jev_kwargs(is_significant_reintroduction=prob))
    assert result.is_significant_reintroduction == prob
    assert result.cached is False
    assert result.current_alignment is AlignmentChoice.ALLY


@pytest.mark.parametrize("prob", [-0.01, 1.01, 5.0])
def test_jev_prob_rejects_out_of_range(prob: float) -> None:
    with pytest.raises(ValidationError):
        JevEvaluationResult(**_jev_kwargs(is_significant_reintroduction=prob))


@pytest.mark.parametrize("score", [0, 3, 5])
def test_jev_score_accepts_bounds(score: int) -> None:
    result = JevEvaluationResult(**_jev_kwargs(requires_context_refresher=score))
    assert result.requires_context_refresher == score


@pytest.mark.parametrize("score", [-1, 6, 10])
def test_jev_score_rejects_out_of_range(score: int) -> None:
    with pytest.raises(ValidationError):
        JevEvaluationResult(**_jev_kwargs(requires_context_refresher=score))


def test_jev_rejects_unknown_alignment() -> None:
    with pytest.raises(ValidationError):
        JevEvaluationResult(**_jev_kwargs(current_alignment="villainous"))


def test_jev_json_roundtrip() -> None:
    original = JevEvaluationResult(**_jev_kwargs(cached=True))
    restored = JevEvaluationResult.model_validate_json(original.model_dump_json())
    assert restored == original


# ── Ledger models ─────────────────────────────────────────


def test_lore_entity_defaults_and_mentions() -> None:
    mention = EntityMention(
        chapter_index=0,
        chapter_title="Chapter One",
        paragraph_index=1,
        char_offset=14,
        excerpt="Vasquez led the fleet.",
        estimated_page=1,
    )
    entity = LoreEntity(
        slug="vasquez",
        canonical_name="Vasquez",
        first_seen_chapter=0,
        first_seen_page=1,
        mentions=[mention],
    )
    assert entity.category is EntityCategory.CHARACTER
    assert entity.aliases == []
    assert entity.mentions[0].excerpt == "Vasquez led the fleet."
    # default_factory must not share state between instances
    other = LoreEntity(
        slug="x", canonical_name="X", first_seen_chapter=0, first_seen_page=0
    )
    assert other.aliases is not entity.aliases


def test_entity_mention_rejects_negative_chapter() -> None:
    with pytest.raises(ValidationError):
        EntityMention(
            chapter_index=-1,
            chapter_title="Bad",
            paragraph_index=0,
            char_offset=0,
            excerpt="",
            estimated_page=0,
        )


def test_candidate_reintroduction_requires_prior_excerpts() -> None:
    candidate = CandidateReintroduction(
        entity_slug="vasquez",
        canonical_name="Vasquez",
        current_chapter_index=3,
        current_chapter_title="Chapter Four",
        current_paragraph_index=0,
        current_scene_text="The ships were led by Vasquez...",
        last_seen_chapter_index=0,
        pages_absent=40,
        prior_excerpts=["Vasquez led the fleet."],
    )
    assert candidate.prior_excerpts == ["Vasquez led the fleet."]
    with pytest.raises(ValidationError):
        CandidateReintroduction(
            **candidate.model_dump(exclude={"prior_excerpts"}),
        )


# ── CairnFootnote & BakeJobState ──────────────────────────


def test_cairn_footnote_defaults_enabled() -> None:
    footnote = CairnFootnote(**_footnote_kwargs())
    assert footnote.enabled is True


@pytest.mark.parametrize(
    "overrides", [{"jev_prob": 1.5}, {"jev_score": 6}, {"alignment": "evil"}]
)
def test_cairn_footnote_rejects_invalid(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CairnFootnote(**_footnote_kwargs(**overrides))


def test_bake_job_state_defaults() -> None:
    state = BakeJobState(
        job_id="job-1",
        filename="sample_novel.epub",
        book_title="Sample Novel",
        book_author="Anon",
        total_chapters=5,
        total_words=5000,
        estimated_pages=20,
    )
    assert state.phase is JobPhase.UPLOADED
    assert state.min_page_gap == 30
    assert state.scanned_chapters == 0
    assert state.entities_tracked == 0
    assert state.footnotes == []
    assert state.output_epub_path is None
    assert state.output_kfx_path is None
    assert state.error_message is None


def test_bake_job_state_nested_footnote_roundtrip() -> None:
    state = BakeJobState.model_validate(
        {
            "job_id": "job-2",
            "filename": "b.epub",
            "book_title": "B",
            "book_author": "A",
            "total_chapters": 5,
            "total_words": 100,
            "estimated_pages": 1,
            "phase": "PROOF_READY",
            "footnotes": [_footnote_kwargs()],
        }
    )
    restored = BakeJobState.model_validate_json(state.model_dump_json())
    assert restored.phase is JobPhase.PROOF_READY
    assert restored.footnotes[0].anchor_id == "cairn-vasquez-ch3"


def test_bake_job_state_rejects_unknown_phase() -> None:
    with pytest.raises(ValidationError):
        BakeJobState.model_validate(
            {
                "job_id": "j",
                "filename": "f",
                "book_title": "t",
                "book_author": "a",
                "total_chapters": 1,
                "total_words": 1,
                "estimated_pages": 1,
                "phase": "DONE",
            }
        )
