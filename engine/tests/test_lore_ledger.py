"""Unit tests for the Chronological Lore Ledger (Task 2.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.config import WORDS_PER_PAGE
from engine.core.epub_parser import ParsedBook, ParsedChapter, parse_epub
from engine.core.lore_ledger import LoreLedger, slugify
from engine.models.schemas import CandidateReintroduction, EntityCategory

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_EPUB_PATH = FIXTURES_DIR / "sample_novel.epub"

# ── Helpers ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def sample_book() -> ParsedBook:
    return parse_epub(SAMPLE_EPUB_PATH)


@pytest.fixture(scope="module")
def ledger(sample_book: ParsedBook) -> LoreLedger:
    return LoreLedger(sample_book)


def _filler(pages: int) -> list[str]:
    """Entity-free lowercase paragraphs totalling ``pages`` estimated pages."""
    words_per_para = 250
    para = " ".join(
        ["the wind moved over quiet empty fields"] * (words_per_para // 7 + 1)
    )
    para = " ".join(para.split()[:words_per_para]) + "."
    return [para] * (pages * WORDS_PER_PAGE // words_per_para)


def _chapter(index: int, paragraphs: list[str]) -> ParsedChapter:
    wc = sum(len(p.split()) for p in paragraphs)
    return ParsedChapter(
        index=index,
        title=f"Chapter {index + 1}",
        file_name=f"chapter_{index + 1}.xhtml",
        paragraphs=paragraphs,
        word_count=wc,
        estimated_pages=max(1, -(-wc // WORDS_PER_PAGE)),
    )


@pytest.fixture(scope="module")
def padded_book() -> ParsedBook:
    """Long synthetic book: Vasquez in Ch1, absent Ch2-3 (~60 pages), back Ch4-5."""
    chapters = [
        _chapter(
            0,
            ["High Marshal Vasquez held the north gate of Oakhaven.", *_filler(5)],
        ),
        _chapter(1, [*_filler(30), "The courier Zephyr reached the camp at dusk."]),
        _chapter(2, _filler(30)),
        _chapter(
            3,
            [
                *_filler(2),
                "Smoke rose over the ridge.",
                "Vasquez returned with five hundred riders.",
                "SCENE-AFTER-MENTION: the riders scattered the enemy.",
            ],
        ),
        _chapter(
            4,
            [
                "Vasquez revealed the SECRET-CH5-FACT that the king was dead.",
                *_filler(3),
            ],
        ),
    ]
    total = sum(c.word_count for c in chapters)
    return ParsedBook(
        title="Padded",
        author="Test",
        chapters=chapters,
        total_chapters=len(chapters),
        total_words=total,
        estimated_pages=-(-total // WORDS_PER_PAGE),
    )


# ── Entity extraction ─────────────────────────────────────


def test_slugify() -> None:
    assert slugify("High Marshal Vasquez") == "high-marshal-vasquez"
    assert slugify("  Ashen   Wastes! ") == "ashen-wastes"


def test_extracts_expected_entities(ledger: LoreLedger) -> None:
    names = {e.canonical_name for e in ledger.entities.values()}
    for expected in (
        "Vasquez",
        "Thorne",
        "Jennifer",
        "Cheryl",
        "Dennis",
        "Oakhaven",
        "Obsidian Banner",
        "Ashen Wastes",
        "Morndun",
    ):
        assert expected in names, f"missing entity {expected}"


def test_no_sentence_initial_false_positives(ledger: LoreLedger) -> None:
    names = {e.canonical_name for e in ledger.entities.values()}
    for junk in ("The", "Hold", "Victory", "Deep", "Thousands", "She", "Nothing",
                 "Just", "Forward", "Three", "High", "Commander"):  # fmt: skip
        assert junk not in names


def test_honorific_alias_resolution(ledger: LoreLedger) -> None:
    vasquez = ledger.get_entity("Vasquez")
    assert vasquez is not None
    assert vasquez.slug == "high-marshal-vasquez"
    assert "High Marshal Vasquez" in vasquez.aliases
    assert vasquez.category == EntityCategory.CHARACTER
    assert vasquez.first_seen_chapter == 0
    # Mentions recorded in chapters 1, 4, 5 (0-based 0, 3, 4) only.
    assert sorted({m.chapter_index for m in vasquez.mentions}) == [0, 3, 4]
    assert ledger.get_entity("high-marshal-vasquez") is vasquez


def test_categories(ledger: LoreLedger) -> None:
    def cat(name: str) -> EntityCategory:
        entity = ledger.get_entity(name)
        assert entity is not None
        return entity.category

    assert cat("Obsidian Banner") == EntityCategory.FACTION
    assert cat("Ashen Wastes") == EntityCategory.LOCATION
    assert cat("Oakhaven") == EntityCategory.LOCATION
    assert cat("Dawn Crown") == EntityCategory.ARTIFACT_OR_LORE


def test_mentions_are_chronological_with_verbatim_excerpts(
    ledger: LoreLedger, sample_book: ParsedBook
) -> None:
    for entity in ledger.entities.values():
        keys = [
            (m.chapter_index, m.paragraph_index, m.char_offset) for m in entity.mentions
        ]
        assert keys == sorted(keys)
        for m in entity.mentions:
            para = sample_book.chapters[m.chapter_index].paragraphs[m.paragraph_index]
            assert m.excerpt in para
            assert m.estimated_page >= 1


def test_lexicon_is_built_incrementally() -> None:
    """A name first confirmed in a later chapter must not be back-filled earlier."""
    book = ParsedBook(
        title="t",
        author="a",
        chapters=[
            _chapter(0, ["Zephyr arrived at noon."]),  # sentence-initial, unconfirmed
            _chapter(1, ["At dusk the envoy Zephyr departed."]),
        ],
    )
    zephyr = LoreLedger(book).get_entity("Zephyr")
    assert zephyr is not None
    assert zephyr.first_seen_chapter == 1


# ── Candidate reintroductions ─────────────────────────────


def test_fixture_reintroduction_detected(ledger: LoreLedger) -> None:
    candidates = ledger.find_candidate_reintroductions(3, min_page_gap=0)
    by_slug = {c.entity_slug: c for c in candidates}
    assert "high-marshal-vasquez" in by_slug
    c = by_slug["high-marshal-vasquez"]
    assert isinstance(c, CandidateReintroduction)
    assert c.canonical_name == "Vasquez"
    assert c.current_chapter_index == 3
    assert c.last_seen_chapter_index == 0
    assert c.prior_excerpts
    assert all("Vasquez" in e for e in c.prior_excerpts)


def test_first_introductions_are_not_candidates(ledger: LoreLedger) -> None:
    slugs = {
        c.entity_slug for c in ledger.find_candidate_reintroductions(4, min_page_gap=0)
    }
    assert "chancellor-dennis" not in slugs  # First appears in Ch5
    assert all(c.entity_slug != "high-marshal-vasquez" for c in
               ledger.find_candidate_reintroductions(1, min_page_gap=0))  # fmt: skip


def test_min_page_gap_filters_short_absences(ledger: LoreLedger) -> None:
    # Fixture is tiny (~2 pages), so the default 30-page gap yields nothing.
    assert ledger.find_candidate_reintroductions(3) == []
    assert ledger.find_candidate_reintroductions(3, min_page_gap=100) == []


def test_padded_book_long_absence(padded_book: ParsedBook) -> None:
    led = LoreLedger(padded_book)
    ch4 = led.find_candidate_reintroductions(3, min_page_gap=30)
    assert [c.entity_slug for c in ch4] == ["high-marshal-vasquez"]
    assert ch4[0].pages_absent >= 60
    assert ch4[0].last_seen_chapter_index == 0
    # Vasquez also appears in Ch4, so Ch5 is NOT a long-absence reintroduction.
    assert led.find_candidate_reintroductions(4, min_page_gap=30) == []


def test_scene_text_bounded_by_reader_position(padded_book: ParsedBook) -> None:
    led = LoreLedger(padded_book)
    (c,) = led.find_candidate_reintroductions(3, min_page_gap=30)
    assert "Vasquez returned" in c.current_scene_text
    assert "SCENE-AFTER-MENTION" not in c.current_scene_text
    assert "SECRET-CH5-FACT" not in c.current_scene_text
    assert len(c.current_scene_text.split()) <= 1500 + 250


def test_invalid_chapter_index_raises(ledger: LoreLedger) -> None:
    with pytest.raises(ValueError):
        ledger.find_candidate_reintroductions(-1)
    with pytest.raises(ValueError):
        ledger.find_candidate_reintroductions(99)
    with pytest.raises(ValueError):
        ledger.snapshot_before(5)


# ── Zero-Spoiler Guarantee ────────────────────────────────


@pytest.mark.parametrize("query_chapter", [2, 3])  # Chapter 3 and Chapter 4 (0-based)
def test_chapter5_facts_never_leak_into_ch3_or_ch4(
    ledger: LoreLedger, sample_book: ParsedBook, query_chapter: int
) -> None:
    """Explicit spoiler test: nothing from Chapter 5 is visible from Ch3/Ch4 queries."""
    ch5 = sample_book.chapters[4]
    ch5_facts = [
        "Chancellor Dennis",
        "Victory at Red Ridge",
        "grand map table",
        "has retreated",
        "true war had only just begun",
    ]
    for fact in ch5_facts:
        assert fact in " ".join(ch5.paragraphs)  # sanity: they really are Ch5 facts

    exposed: list[str] = []
    for c in ledger.find_candidate_reintroductions(query_chapter, min_page_gap=0):
        exposed.extend(c.prior_excerpts)
        exposed.append(c.current_scene_text)
    snapshot = ledger.snapshot_before(query_chapter)
    for entity in snapshot.values():
        exposed.extend(m.excerpt for m in entity.mentions)
        assert all(m.chapter_index < query_chapter for m in entity.mentions)
    for slug in ledger.entities:
        exposed.extend(ledger.get_prior_excerpts(slug, query_chapter))

    blob = "\n".join(exposed)
    for fact in ch5_facts:
        assert fact not in blob, f"Ch5 fact leaked into Ch{query_chapter + 1}: {fact!r}"
    for ch5_paragraph in ch5.paragraphs:
        assert ch5_paragraph not in blob

    # Ch5-only entities must not exist in the reader's knowledge at Ch3/Ch4.
    assert "chancellor-dennis" not in snapshot
    assert "spire" not in snapshot


def test_prior_excerpts_strictly_from_earlier_chapters(
    ledger: LoreLedger, sample_book: ParsedBook
) -> None:
    for n in range(sample_book.total_chapters):
        allowed = "\n".join(p for ch in sample_book.chapters[:n] for p in ch.paragraphs)
        for slug in ledger.entities:
            for excerpt in ledger.get_prior_excerpts(slug, n):
                assert excerpt in allowed, (
                    f"excerpt not from chapters < {n}: {excerpt!r}"
                )
        for c in ledger.find_candidate_reintroductions(n, min_page_gap=0):
            assert c.last_seen_chapter_index < n
            for excerpt in c.prior_excerpts:
                assert excerpt in allowed


def test_padded_book_secret_never_in_ch4_context(padded_book: ParsedBook) -> None:
    led = LoreLedger(padded_book)
    (c,) = led.find_candidate_reintroductions(3, min_page_gap=30)
    assert all("SECRET-CH5-FACT" not in e for e in c.prior_excerpts)
    assert all(
        "Vasquez returned" not in e for e in c.prior_excerpts
    )  # Ch4 itself excluded
    assert c.prior_excerpts == ["High Marshal Vasquez held the north gate of Oakhaven."]
