"""Chronological Lore Ledger for CairnBooks.

Deterministically extracts named entities (characters, factions, locations,
lore terms) chapter by chapter, records every mention with its estimated page,
and surfaces *candidate reintroductions*: entities that resurface in Chapter
``N`` after an absence of at least ``min_page_gap`` pages.

Zero-Spoiler Guarantee (AGENTS.md invariant 1)
----------------------------------------------
* ``prior_excerpts`` and ledger snapshots for Chapter ``N`` are drawn strictly
  from chapters ``< N``.
* ``current_scene_text`` is bounded by the reader's position: it contains only
  Chapter ``N`` paragraphs up to and including the mention paragraph.
* The proper-noun lexicon used for tokenisation is grown incrementally, so
  extraction for Chapter ``k`` never depends on text from chapters ``> k``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.config import DEFAULT_MIN_PAGE_GAP, WORDS_PER_PAGE
from engine.core.epub_parser import ParsedBook
from engine.models.schemas import (
    CandidateReintroduction,
    EntityCategory,
    EntityMention,
    LoreEntity,
)

# ── Lexical heuristics ────────────────────────────────────

HONORIFICS: tuple[tuple[str, ...], ...] = tuple(
    sorted(
        (
            tuple(h.split())
            for h in (
                "High Marshal",
                "Marshal",
                "Commander",
                "Captain",
                "General",
                "Scout",
                "Scholar",
                "Chancellor",
                "Lord",
                "Lady",
                "King",
                "Queen",
                "Prince",
                "Princess",
                "Sir",
                "Dame",
                "Doctor",
                "Dr",
                "Master",
                "Mistress",
            )
        ),
        key=len,
        reverse=True,  # Match the longest honorific first ("High Marshal").
    )
)

# Capitalised words that are never entity names on their own.
STOPWORDS: frozenset[str] = frozenset(
    {
        "A", "An", "The", "I", "He", "She", "It", "We", "They", "You", "His",
        "Her", "Its", "Our", "Their", "My", "Your", "This", "That", "These",
        "Those", "And", "But", "Or", "Nor", "So", "Yet", "If", "Then", "When",
        "While", "Where", "What", "Who", "Why", "How", "There", "Here", "In",
        "On", "At", "Of", "To", "For", "From", "By", "With", "As", "Not", "No",
        "Yes", "Chapter", "Mr", "Mrs", "Ms",
    }
)  # fmt: skip

FACTION_WORDS: frozenset[str] = frozenset(
    {"Banner", "Faction", "Order", "Guild", "Legion", "Clan", "House", "Empire",
     "Council", "Brotherhood", "Sisterhood", "Covenant", "Army", "Host"}
)  # fmt: skip
LOCATION_WORDS: frozenset[str] = frozenset(
    {"Wastes", "Ridge", "Spire", "Valley", "River", "Mountains", "Mountain",
     "Citadel", "Keep", "Forest", "Sea", "City", "Isles", "Pass", "Vale",
     "Hold", "Fortress", "Tower", "Gate", "Plains", "Woods", "Bay", "Harbor"}
)  # fmt: skip
ARTIFACT_WORDS: frozenset[str] = frozenset(
    {"Crown", "Sword", "Blade", "Codex", "Codices", "Pact", "Pacts", "Stone",
     "Ring", "Tome", "Relic", "Throne", "Shard", "Archive"}
)  # fmt: skip
LOCATIVE_PREPOSITIONS: frozenset[str] = frozenset(
    {"of", "in", "at", "to", "from", "within", "toward", "towards", "near",
     "beyond", "across", "into"}
)  # fmt: skip

_CAP_SPAN_RE = re.compile(
    r"[A-Z][A-Za-z\-]*(?:['\u2019][A-Za-z]+)?(?:\s+[A-Z][A-Za-z\-]*(?:['\u2019][A-Za-z]+)?)*"
)
_CAP_WORD_RE = re.compile(r"[A-Z][A-Za-z\-]*")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+[\"'\u201d\u2019)]*|[^.!?]+$")
_OPENERS = "\"'\u201c\u2018(["
_POSSESSIVE_RE = re.compile(r"['\u2019]s$")
_MAX_SCENE_WORDS = 1500  # ~2,000 tokens
DEFAULT_MAX_PRIOR_EXCERPTS = 8


def slugify(text: str) -> str:
    """Lowercase, hyphen-separated, ASCII-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "entity"


def _is_sentence_initial(text: str, start: int) -> bool:
    """True when ``text[start]`` begins a sentence (ignoring quotes / spaces)."""
    i = start - 1
    while i >= 0 and (
        text[i].isspace() or text[i] in _OPENERS or text[i] in "\u201d\u2019"
    ):
        i -= 1
    return i < 0 or text[i] in ".!?:;\u2014"


def _sentence_at(paragraph: str, offset: int) -> str:
    """Return the verbatim sentence in ``paragraph`` that contains ``offset``."""
    for match in _SENTENCE_RE.finditer(paragraph):
        if match.start() <= offset < match.end():
            return match.group().strip()
    return paragraph.strip()


def _strip_honorific(words: list[str]) -> tuple[list[str], bool]:
    for honorific in HONORIFICS:
        n = len(honorific)
        if len(words) > n and tuple(words[:n]) == honorific:
            return words[n:], True
    return words, False


@dataclass(frozen=True)
class _RawMention:
    surface: str  # Full surface form, e.g. "High Marshal Vasquez"
    canonical: str  # Canonical name, e.g. "Vasquez"
    has_honorific: bool
    offset: int  # Char offset of ``surface`` within the paragraph
    preceding_word: str


class LoreLedger:
    """Chronological index of entities and mentions across a parsed book."""

    def __init__(
        self,
        book: ParsedBook,
        max_prior_excerpts: int = DEFAULT_MAX_PRIOR_EXCERPTS,
    ) -> None:
        self.book = book
        self.max_prior_excerpts = max_prior_excerpts
        self.entities: dict[str, LoreEntity] = {}  # slug -> entity
        self._key_to_slug: dict[str, str] = {}  # lowercase canonical -> slug
        self._lexicon: set[str] = set()  # Proper nouns confirmed so far
        self._paragraph_pages: list[list[int]] = []  # [chapter][paragraph] -> page
        self._build()

    # ── Construction ──────────────────────────────────────

    def _build(self) -> None:
        words_before = 0
        for chapter in self.book.chapters:
            # Grow the lexicon with mid-sentence capitalised words from THIS
            # chapter only (never from later chapters).
            for paragraph in chapter.paragraphs:
                for m in _CAP_WORD_RE.finditer(paragraph):
                    if m.group() not in STOPWORDS and not _is_sentence_initial(
                        paragraph, m.start()
                    ):
                        self._lexicon.add(m.group())

            pages: list[int] = []
            for p_idx, paragraph in enumerate(chapter.paragraphs):
                page = words_before // WORDS_PER_PAGE + 1
                pages.append(page)
                for raw in self._extract_raw_mentions(paragraph):
                    self._record(
                        raw, chapter.index, chapter.title, p_idx, paragraph, page
                    )
                words_before += len(paragraph.split())
            self._paragraph_pages.append(pages)

    def _extract_raw_mentions(self, paragraph: str) -> list[_RawMention]:
        results: list[_RawMention] = []
        for span in _CAP_SPAN_RE.finditer(paragraph):
            words = [_POSSESSIVE_RE.sub("", w) for w in span.group().split()]
            start = span.start()

            # Drop leading stopwords and unconfirmed sentence-initial words.
            while words:
                first = words[0]
                initial = _is_sentence_initial(paragraph, start)
                is_honorific_lead = _strip_honorific(words)[1]
                drop = first in STOPWORDS or (
                    initial
                    and not is_honorific_lead
                    and first not in self._lexicon
                    and first.lower() not in self._key_to_slug
                )
                if not drop:
                    break
                consumed = paragraph.index(first, start) + len(first)
                words = words[1:]
                rest = paragraph[consumed:]
                start = consumed + (len(rest) - len(rest.lstrip()))
            if not words:
                continue

            name_words, has_honorific = _strip_honorific(words)
            if (
                not has_honorific
                and len(words) == 1
                and any(h == (words[0],) for h in HONORIFICS)
            ):
                continue  # Bare honorific ("Commander") is not an entity.

            prefix = paragraph[:start].split()
            preceding = prefix[-1].lower() if prefix else ""
            results.append(
                _RawMention(
                    surface=" ".join(words),
                    canonical=" ".join(name_words),
                    has_honorific=has_honorific,
                    offset=start,
                    preceding_word=preceding,
                )
            )
        return results

    @staticmethod
    def _categorise(raw: _RawMention) -> EntityCategory:
        if raw.has_honorific:
            return EntityCategory.CHARACTER
        last = raw.canonical.split()[-1]
        if last in FACTION_WORDS:
            return EntityCategory.FACTION
        if last in LOCATION_WORDS:
            return EntityCategory.LOCATION
        if last in ARTIFACT_WORDS:
            return EntityCategory.ARTIFACT_OR_LORE
        if raw.preceding_word in LOCATIVE_PREPOSITIONS:
            return EntityCategory.LOCATION
        return EntityCategory.CHARACTER

    def _record(
        self,
        raw: _RawMention,
        chapter_index: int,
        chapter_title: str,
        paragraph_index: int,
        paragraph: str,
        page: int,
    ) -> None:
        key = raw.canonical.lower()
        slug = self._key_to_slug.get(key)
        if slug is None:
            slug = slugify(raw.surface)
            base, n = slug, 2
            while slug in self.entities:
                slug, n = f"{base}-{n}", n + 1
            self._key_to_slug[key] = slug
            self.entities[slug] = LoreEntity(
                slug=slug,
                canonical_name=raw.canonical,
                category=self._categorise(raw),
                first_seen_chapter=chapter_index,
                first_seen_page=page,
            )
        entity = self.entities[slug]
        for alias in {raw.surface, raw.canonical}:
            if alias != entity.canonical_name and alias not in entity.aliases:
                entity.aliases.append(alias)

        entity.mentions.append(
            EntityMention(
                chapter_index=chapter_index,
                chapter_title=chapter_title,
                paragraph_index=paragraph_index,
                char_offset=raw.offset,
                excerpt=_sentence_at(paragraph, raw.offset),
                estimated_page=page,
            )
        )

    # ── Queries (all temporally bounded) ──────────────────

    def _check_chapter(self, chapter_index: int) -> None:
        if not 0 <= chapter_index < len(self.book.chapters):
            raise ValueError(
                f"chapter_index {chapter_index} out of range "
                f"[0, {len(self.book.chapters) - 1}]"
            )

    def get_entity(self, name_or_slug: str) -> LoreEntity | None:
        if name_or_slug in self.entities:
            return self.entities[name_or_slug]
        slug = self._key_to_slug.get(name_or_slug.lower())
        return self.entities.get(slug) if slug else None

    def snapshot_before(self, chapter_index: int) -> dict[str, LoreEntity]:
        """Ledger as known to a reader *starting* ``chapter_index`` (chapters < N)."""
        self._check_chapter(chapter_index)
        snapshot: dict[str, LoreEntity] = {}
        for slug, entity in self.entities.items():
            prior = [m for m in entity.mentions if m.chapter_index < chapter_index]
            if prior:
                snapshot[slug] = entity.model_copy(
                    update={"mentions": prior}, deep=True
                )
        return snapshot

    def get_prior_excerpts(self, entity_slug: str, chapter_index: int) -> list[str]:
        """Most recent unique excerpts for an entity, strictly from chapters < N."""
        self._check_chapter(chapter_index)
        entity = self.entities.get(entity_slug)
        if entity is None:
            return []
        excerpts: list[str] = []
        for m in entity.mentions:
            if m.chapter_index >= chapter_index:
                continue  # Hard spoiler cutoff.
            if m.excerpt not in excerpts:
                excerpts.append(m.excerpt)
        return (
            excerpts[-self.max_prior_excerpts :]
            if self.max_prior_excerpts
            else excerpts
        )

    def _scene_text(self, chapter_index: int, paragraph_index: int) -> str:
        """Chapter-N text up to and including the mention paragraph (~1,500 words)."""
        paragraphs = self.book.chapters[chapter_index].paragraphs[: paragraph_index + 1]
        selected: list[str] = []
        total = 0
        for paragraph in reversed(paragraphs):
            selected.insert(0, paragraph)
            total += len(paragraph.split())
            if total >= _MAX_SCENE_WORDS:
                break
        return "\n\n".join(selected)

    def find_candidate_reintroductions(
        self,
        chapter_index: int,
        min_page_gap: int = DEFAULT_MIN_PAGE_GAP,
    ) -> list[CandidateReintroduction]:
        """Entities resurfacing in ``chapter_index`` after >= ``min_page_gap`` pages."""
        self._check_chapter(chapter_index)
        chapter = self.book.chapters[chapter_index]
        candidates: list[CandidateReintroduction] = []

        for slug, entity in self.entities.items():
            current = [m for m in entity.mentions if m.chapter_index == chapter_index]
            prior = [m for m in entity.mentions if m.chapter_index < chapter_index]
            if not current or not prior:
                continue  # Absent this chapter, or a first introduction.

            first_current = current[0]
            last_prior = prior[-1]
            pages_absent = max(
                0, first_current.estimated_page - last_prior.estimated_page
            )
            if pages_absent < min_page_gap:
                continue

            prior_excerpts = self.get_prior_excerpts(slug, chapter_index)
            candidates.append(
                CandidateReintroduction(
                    entity_slug=slug,
                    canonical_name=entity.canonical_name,
                    current_chapter_index=chapter_index,
                    current_chapter_title=chapter.title,
                    current_paragraph_index=first_current.paragraph_index,
                    current_scene_text=self._scene_text(
                        chapter_index, first_current.paragraph_index
                    ),
                    last_seen_chapter_index=last_prior.chapter_index,
                    pages_absent=pages_absent,
                    prior_excerpts=prior_excerpts,
                )
            )

        candidates.sort(key=lambda c: (c.current_paragraph_index, c.entity_slug))
        return candidates


def build_ledger(book: ParsedBook) -> LoreLedger:
    """Convenience constructor."""
    return LoreLedger(book)
