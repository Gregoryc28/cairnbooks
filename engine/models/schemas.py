"""Pydantic v2 data contracts for CairnBooks (PROJECT_SPEC §4)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ── 4.1 Lore Ledger & Entity Tracking ─────────────────────


class AlignmentChoice(str, Enum):
    ALLY = "ally"
    ADVERSARY = "adversary"
    NEUTRAL = "neutral"
    AMBIGUOUS = "ambiguous"


class EntityCategory(str, Enum):
    CHARACTER = "character"
    FACTION = "faction"
    LOCATION = "location"
    ARTIFACT_OR_LORE = "artifact_or_lore"


class EntityMention(BaseModel):
    chapter_index: int = Field(ge=0)  # 0-based linear spine order
    chapter_title: str
    paragraph_index: int = Field(ge=0)
    char_offset: int = Field(ge=0)
    excerpt: str  # Verbatim 1-2 sentence context from this chapter
    estimated_page: int = Field(ge=0)  # Calculated at 250 words/page


class LoreEntity(BaseModel):
    slug: str  # e.g., "high-marshal-vasquez"
    canonical_name: str  # e.g., "Vasquez"
    aliases: list[str] = Field(default_factory=list)
    category: EntityCategory = EntityCategory.CHARACTER
    first_seen_chapter: int = Field(ge=0)
    first_seen_page: int = Field(ge=0)
    mentions: list[EntityMention] = Field(default_factory=list)


class CandidateReintroduction(BaseModel):
    entity_slug: str
    canonical_name: str
    current_chapter_index: int = Field(ge=0)
    current_chapter_title: str
    current_paragraph_index: int = Field(ge=0)
    current_scene_text: str  # ~1,500-2,500 tokens surrounding the mention
    last_seen_chapter_index: int = Field(ge=0)
    pages_absent: int = Field(ge=0)  # Must be >= min_page_gap to qualify
    prior_excerpts: list[str]  # Strictly from chapters < current_chapter_index


# ── 4.2 Tier 1 (Jev Evaluator) & Tier 2 (Synopsis) Contracts ──


class JevEvaluationResult(BaseModel):
    entity_slug: str
    chapter_index: int = Field(ge=0)
    is_significant_reintroduction: float = Field(ge=0.0, le=1.0)  # Jev 'noul'
    requires_context_refresher: int = Field(ge=0, le=5)  # Jev 'score'
    current_alignment: AlignmentChoice  # Jev 'choice'
    provider_used: str  # "jev_native" | "openrouter_fallback" | "mock"
    cached: bool = False


class CairnFootnote(BaseModel):
    anchor_id: str  # e.g., "cairn-vasquez-ch18"
    entity_slug: str
    display_name: str
    chapter_index: int = Field(ge=0)
    chapter_title: str
    paragraph_index: int = Field(ge=0)
    pages_absent: int = Field(ge=0)
    first_seen_chapter: int = Field(ge=0)
    last_seen_chapter: int = Field(ge=0)
    alignment: AlignmentChoice
    jev_prob: float = Field(ge=0.0, le=1.0)
    jev_score: int = Field(ge=0, le=5)
    synopsis_text: str  # <= 15 words generated strictly from prior_excerpts
    enabled: bool = True  # User can toggle off in Stage 3 Proof Sheet


# ── 4.3 Job State & SSE Stream Events ─────────────────────


class JobPhase(str, Enum):
    UPLOADED = "UPLOADED"
    SCANNING = "SCANNING"
    PROOF_READY = "PROOF_READY"
    BAKING = "BAKING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class BakeJobState(BaseModel):
    job_id: str
    filename: str
    book_title: str
    book_author: str
    total_chapters: int = Field(ge=0)
    total_words: int = Field(ge=0)
    estimated_pages: int = Field(ge=0)
    min_page_gap: int = Field(default=30, ge=0)
    phase: JobPhase = JobPhase.UPLOADED
    scanned_chapters: int = Field(default=0, ge=0)
    entities_tracked: int = Field(default=0, ge=0)
    footnotes: list[CairnFootnote] = Field(default_factory=list)
    output_epub_path: str | None = None
    output_kfx_path: str | None = None
    error_message: str | None = None
