"""Unit tests for Bidirectional EPUB 3 Footnote DOM Injector (Task 4.1)."""

from __future__ import annotations

from pathlib import Path

from lxml import etree  # type: ignore[import-untyped]

from engine.core.dom_injector import (
    EPUB_NS,
    EPUB_TYPE_ATTR,
    inject_chapter_footnotes,
    inject_footnotes_into_epub,
)
from engine.core.epub_parser import parse_epub
from engine.models.schemas import AlignmentChoice, CairnFootnote

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_EPUB_PATH = FIXTURES_DIR / "sample_novel.epub"

SAMPLE_CHAPTER_XHTML = """<html><head><title>Chapter Four: The Battle of Red Ridge</title></head><body>
<h1>Chapter Four: The Battle of Red Ridge</h1>
<p>The southern defensive line crumbled beneath the weight of enemy cavalry.</p>
<p>High Marshal Vasquez charged into the breach at the head of five hundred armored cataphracts.</p>
<p>"Forward for the Dawn Crown!" Vasquez roared, turning the tide of the engagement.</p>
</body></html>"""


def _make_footnote(**overrides: object) -> CairnFootnote:
    data: dict[str, object] = {
        "anchor_id": "cairn-high-marshal-vasquez-ch4",
        "entity_slug": "high-marshal-vasquez",
        "display_name": "Vasquez",
        "chapter_index": 3,  # 0-based -> ch4 in markup
        "chapter_title": "Chapter Four: The Battle of Red Ridge",
        "paragraph_index": 1,
        "pages_absent": 45,
        "first_seen_chapter": 0,
        "last_seen_chapter": 0,
        "alignment": AlignmentChoice.ALLY,
        "jev_prob": 0.91,
        "jev_score": 5,
        "synopsis_text": "Oakhaven garrison commander who defended the north bastion in Ch. 1.",
        "enabled": True,
    }
    data.update(overrides)
    return CairnFootnote.model_validate(data)


def test_bidirectional_noteref_and_aside_markup_valid_xml() -> None:
    footnote = _make_footnote()
    updated_xhtml, count = inject_chapter_footnotes(SAMPLE_CHAPTER_XHTML, [footnote])

    assert count == 1

    # Strict XML parse via lxml.etree (no recover mode)
    strict_parser = etree.XMLParser(recover=False)
    root = etree.fromstring(updated_xhtml.encode("utf-8"), parser=strict_parser)

    ns = {"x": "http://www.w3.org/1999/xhtml", "epub": EPUB_NS}

    # 1. Verify inline <a epub:type="noteref" role="doc-noteref">
    anchors = root.xpath("//x:a[@class='cairn-anchor']", namespaces=ns)
    assert len(anchors) == 1
    anchor = anchors[0]
    assert anchor.get("id") == "ref-high-marshal-vasquez-ch4"
    assert anchor.get("href") == "#note-high-marshal-vasquez-ch4"
    assert anchor.get(EPUB_TYPE_ATTR) == "noteref"
    assert anchor.get("role") == "doc-noteref"
    assert anchor.text == "Vasquez"

    sup_els = anchor.xpath("./x:sup", namespaces=ns)
    assert len(sup_els) == 1
    assert sup_els[0].text == "[?]"

    # 2. Verify footer <aside epub:type="footnote" role="doc-footnote">
    asides = root.xpath("//x:aside[@class='cairn-footnote-item']", namespaces=ns)
    assert len(asides) == 1
    aside = asides[0]
    assert aside.get("id") == "note-high-marshal-vasquez-ch4"
    assert aside.get(EPUB_TYPE_ATTR) == "footnote"
    assert aside.get("role") == "doc-footnote"

    aside_text = "".join(aside.itertext())
    assert "Vasquez" in aside_text
    assert "Oakhaven garrison commander" in aside_text

    # 3. Verify bidirectional backlink <a href="#ref-..." role="doc-backlink">
    backlinks = aside.xpath(".//x:a[@role='doc-backlink']", namespaces=ns)
    assert len(backlinks) == 1
    assert backlinks[0].get("href") == "#ref-high-marshal-vasquez-ch4"
    assert backlinks[0].text == "\u21a9"


def test_only_first_mention_per_chapter_is_wrapped() -> None:
    """Vasquez appears in paragraph 1 and paragraph 2; only the first mention is wrapped."""
    footnote = _make_footnote()
    updated_xhtml, count = inject_chapter_footnotes(SAMPLE_CHAPTER_XHTML, [footnote])

    assert count == 1
    root = etree.fromstring(updated_xhtml.encode("utf-8"))
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    anchors = root.xpath("//x:a[@class='cairn-anchor']", namespaces=ns)
    assert len(anchors) == 1

    # Second paragraph with Vasquez remains unwrapped plain text
    paragraphs = root.xpath("//x:body/x:p", namespaces=ns)
    third_para_text = "".join(paragraphs[2].itertext())
    assert '"Forward for the Dawn Crown!" Vasquez roared' in third_para_text
    assert paragraphs[2].xpath(".//x:a[@class='cairn-anchor']", namespaces=ns) == []


def test_disabled_footnotes_are_skipped() -> None:
    disabled_note = _make_footnote(enabled=False)
    updated_xhtml, count = inject_chapter_footnotes(
        SAMPLE_CHAPTER_XHTML, [disabled_note]
    )
    assert count == 0
    assert updated_xhtml == SAMPLE_CHAPTER_XHTML


def test_inject_footnotes_into_epub_archive(tmp_path: Path) -> None:
    out_epub = tmp_path / "enhanced_sample.epub"
    footnotes = [
        _make_footnote(
            chapter_index=3,
            paragraph_index=1,
        ),
        _make_footnote(
            anchor_id="cairn-scout-jennifer-ch5",
            entity_slug="scout-jennifer",
            display_name="Jennifer",
            chapter_index=4,
            chapter_title="Chapter Five: Council of the Spire",
            paragraph_index=0,
            pages_absent=35,
            first_seen_chapter=1,
            last_seen_chapter=1,
            synopsis_text="Wilderness scout who trekked across the Ashen Wastes in Ch. 2.",
        ),
    ]

    total = inject_footnotes_into_epub(SAMPLE_EPUB_PATH, out_epub, footnotes)
    assert total == 2
    assert out_epub.exists()

    parsed = parse_epub(out_epub)
    assert parsed.total_chapters == 5

    # Verify both modified chapters parse cleanly through lxml.etree
    strict_parser = etree.XMLParser(recover=False)
    ch4_root = etree.fromstring(
        parsed.chapters[3].raw_html.encode("utf-8"), parser=strict_parser
    )
    ch5_root = etree.fromstring(
        parsed.chapters[4].raw_html.encode("utf-8"), parser=strict_parser
    )

    assert "ref-high-marshal-vasquez-ch4" in parsed.chapters[3].raw_html
    assert "note-high-marshal-vasquez-ch4" in parsed.chapters[3].raw_html
    assert "ref-scout-jennifer-ch5" in parsed.chapters[4].raw_html
    assert "note-scout-jennifer-ch5" in parsed.chapters[4].raw_html
    assert ch4_root is not None
    assert ch5_root is not None
