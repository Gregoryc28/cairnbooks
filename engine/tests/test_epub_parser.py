"""Unit tests for EPUB parser (Task 2.1)."""

from pathlib import Path

from engine.core.epub_parser import ParsedBook, ParsedChapter, parse_epub

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_EPUB_PATH = FIXTURES_DIR / "sample_novel.epub"


def test_fixture_exists() -> None:
    assert SAMPLE_EPUB_PATH.exists(), f"Missing test fixture: {SAMPLE_EPUB_PATH}"


def test_parse_sample_novel() -> None:
    book: ParsedBook = parse_epub(SAMPLE_EPUB_PATH)

    assert book.title == "The Siege of Oakhaven"
    assert book.author == "A. R. Sterling"
    assert book.total_chapters == 5
    assert len(book.chapters) == 5

    # Verify linear sequence and chapter indices
    for idx, chap in enumerate(book.chapters):
        assert isinstance(chap, ParsedChapter)
        assert chap.index == idx
        assert chap.word_count > 0
        assert len(chap.paragraphs) >= 3
        assert chap.raw_html != ""
        assert chap.estimated_pages >= 1

    # Total words should match sum of chapters
    assert book.total_words == sum(c.word_count for c in book.chapters)
    assert book.total_words > 0
    assert book.estimated_pages >= 1


def test_chapter_titles_and_filenames() -> None:
    book: ParsedBook = parse_epub(SAMPLE_EPUB_PATH)

    expected_titles = [
        "Chapter One: The Siege Begins",
        "Chapter Two: The Ashen Wastes",
        "Chapter Three: Archive of Whispers",
        "Chapter Four: The Battle of Red Ridge",
        "Chapter Five: Council of the Spire",
    ]

    for idx, expected in enumerate(expected_titles):
        assert book.chapters[idx].title == expected
        assert book.chapters[idx].file_name == f"chapter_{idx + 1}.xhtml"


def test_narrative_arc_entity_presence() -> None:
    """Verify that Vasquez appears in Ch 1, is absent in Ch 2-3, and returns in Ch 4-5."""
    book: ParsedBook = parse_epub(SAMPLE_EPUB_PATH)

    ch1_text = " ".join(book.chapters[0].paragraphs)
    ch2_text = " ".join(book.chapters[1].paragraphs)
    ch3_text = " ".join(book.chapters[2].paragraphs)
    ch4_text = " ".join(book.chapters[3].paragraphs)
    ch5_text = " ".join(book.chapters[4].paragraphs)

    assert "Vasquez" in ch1_text
    assert "Vasquez" not in ch2_text
    assert "Vasquez" not in ch3_text
    assert "Vasquez" in ch4_text
    assert "Vasquez" in ch5_text
