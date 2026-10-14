"""Bidirectional EPUB 3 Footnote DOM Injector for CairnBooks.

Mutates chapter XHTML using ``lxml`` to inject Kindle Paperwhite KFX-compatible
popup footnote anchors (``epub:type="noteref"``) and matching bottom-sheet
aside cards (``<aside epub:type="footnote">``) with backlinks.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import ebooklib  # type: ignore[import-untyped]
from ebooklib import epub  # type: ignore[import-untyped]
from lxml import etree  # type: ignore[import-untyped]

from engine.models.schemas import CairnFootnote

XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
NSMAP = {None: XHTML_NS, "epub": EPUB_NS}
EPUB_TYPE_ATTR = f"{{{EPUB_NS}}}type"

CAIRN_EINK_CSS = """
/* CairnBooks E-Ink Footnote Styling */
a.cairn-anchor {
  text-decoration: none;
  border-bottom: 1px dotted currentColor;
  color: inherit;
}
a.cairn-anchor sup {
  font-size: 0.72em;
  font-weight: 600;
  margin-left: 0.08em;
}
section.cairn-footnotes {
  margin-top: 2.5em;
  padding-top: 1em;
  border-top: 1px solid currentColor;
  font-size: 0.9em;
}
aside.cairn-footnote-item {
  margin: 0.6em 0;
  line-height: 1.4;
}
a.cairn-backlink {
  margin-left: 0.35em;
  text-decoration: none;
}
""".strip()


def make_ref_id(entity_slug: str, chapter_index: int) -> str:
    """Return the inline anchor ID for an entity in chapter ``chapter_index`` (0-based)."""
    return f"ref-{entity_slug}-ch{chapter_index + 1}"


def make_note_id(entity_slug: str, chapter_index: int) -> str:
    """Return the footnote aside ID for an entity in chapter ``chapter_index`` (0-based)."""
    return f"note-{entity_slug}-ch{chapter_index + 1}"


def _local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _qualify_tag(root: etree._Element, name: str) -> str:
    if isinstance(root.tag, str) and root.tag.startswith("{"):
        ns = root.tag.split("}", 1)[0][1:]
        return f"{{{ns}}}{name}"
    return name


def _parse_xhtml(raw_html: str) -> etree._Element:
    """Parse raw chapter HTML/XHTML into an ``lxml.etree`` root element with ``epub`` namespace."""
    cleaned = raw_html.strip()
    # Ensure xmlns:epub is declared on the root <html ...> element so lxml preserves epub:type
    if "xmlns:epub" not in cleaned:
        cleaned = re.sub(
            r"<html\b([^>]*)>",
            f'<html\\1 xmlns:epub="{EPUB_NS}">',
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
    if "xmlns=" not in cleaned:
        cleaned = re.sub(
            r"<html\b([^>]*)>",
            f'<html\\1 xmlns="{XHTML_NS}">',
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )

    parser = etree.XMLParser(recover=True, remove_blank_text=False)
    root = etree.fromstring(cleaned.encode("utf-8"), parser=parser)
    return root


def _ensure_head_and_style(root: etree._Element) -> None:
    """Ensure a ``<head>`` exists and contains the CairnBooks e-ink ``<style>`` block."""
    head = None
    body = None
    for child in root:
        lname = _local_name(child.tag)
        if lname == "head":
            head = child
        elif lname == "body":
            body = child

    if head is None:
        head = etree.Element(_qualify_tag(root, "head"))
        if body is not None:
            root.insert(list(root).index(body), head)
        else:
            root.insert(0, head)

    for child in head:
        if _local_name(child.tag) == "style" and child.get("id") == "cairnbooks-style":
            return

    style_el = etree.SubElement(
        head,
        _qualify_tag(root, "style"),
        {"id": "cairnbooks-style", "type": "text/css"},
    )
    style_el.text = f"\n{CAIRN_EINK_CSS}\n"


def _build_anchor_element(
    root: etree._Element,
    matched_text: str,
    ref_id: str,
    note_id: str,
) -> etree._Element:
    """Construct ``<a id="ref-..." href="#note-..." epub:type="noteref" role="doc-noteref">``."""
    anchor = etree.Element(
        _qualify_tag(root, "a"),
        {
            "id": ref_id,
            "href": f"#{note_id}",
            EPUB_TYPE_ATTR: "noteref",
            "role": "doc-noteref",
            "class": "cairn-anchor",
        },
    )
    anchor.text = matched_text
    sup = etree.SubElement(anchor, _qualify_tag(root, "sup"))
    sup.text = "[?]"
    return anchor


def _wrap_first_mention_in_element(
    root: etree._Element,
    container: etree._Element,
    display_name: str,
    ref_id: str,
    note_id: str,
) -> bool:
    """Locate the first occurrence of ``display_name`` in ``container`` and wrap it."""
    pattern = re.compile(rf"\b{re.escape(display_name)}\b")

    if container.text:
        match = pattern.search(container.text)
        if match:
            before = container.text[: match.start()]
            matched = container.text[match.start() : match.end()]
            after = container.text[match.end() :]

            anchor = _build_anchor_element(root, matched, ref_id, note_id)
            anchor.tail = after
            container.text = before
            container.insert(0, anchor)
            return True

    for idx, child in enumerate(list(container)):
        lname = _local_name(child.tag)
        if lname not in (
            "a",
            "sup",
            "script",
            "style",
            "aside",
        ) and _wrap_first_mention_in_element(
            root, child, display_name, ref_id, note_id
        ):
            return True

        if child.tail:
            match = pattern.search(child.tail)
            if match:
                before = child.tail[: match.start()]
                matched = child.tail[match.start() : match.end()]
                after = child.tail[match.end() :]

                anchor = _build_anchor_element(root, matched, ref_id, note_id)
                anchor.tail = after
                child.tail = before
                container.insert(idx + 1, anchor)
                return True

    return False


def _append_footnotes_section(
    root: etree._Element,
    body: etree._Element,
    injected: list[tuple[CairnFootnote, str, str]],
) -> None:
    """Append ``<section epub:type="footnotes">`` with ``<aside epub:type="footnote">`` cards."""
    section = etree.SubElement(
        body,
        _qualify_tag(root, "section"),
        {
            EPUB_TYPE_ATTR: "footnotes",
            "role": "doc-endnotes",
            "class": "cairn-footnotes",
        },
    )

    for footnote, ref_id, note_id in injected:
        aside = etree.SubElement(
            section,
            _qualify_tag(root, "aside"),
            {
                "id": note_id,
                EPUB_TYPE_ATTR: "footnote",
                "role": "doc-footnote",
                "class": "cairn-footnote-item",
            },
        )
        p_el = etree.SubElement(aside, _qualify_tag(root, "p"))
        strong = etree.SubElement(p_el, _qualify_tag(root, "strong"))
        strong.text = f"{footnote.display_name} "
        strong.tail = (
            f"({footnote.alignment.value.upper()} \u2022 {footnote.pages_absent}p absent): "
            f"{footnote.synopsis_text} "
        )

        backlink = etree.SubElement(
            p_el,
            _qualify_tag(root, "a"),
            {
                "href": f"#{ref_id}",
                "role": "doc-backlink",
                "class": "cairn-backlink",
            },
        )
        backlink.text = "\u21a9"


def inject_chapter_footnotes(
    raw_html: str,
    footnotes: Iterable[CairnFootnote],
) -> tuple[str, int]:
    """Inject enabled ``CairnFootnote`` anchors and aside cards into a chapter's XHTML.

    Returns ``(modified_xhtml, injected_count)``.
    """
    enabled_notes = [fn for fn in footnotes if fn.enabled]
    if not enabled_notes:
        return raw_html, 0

    root = _parse_xhtml(raw_html)
    body = next((c for c in root if _local_name(c.tag) == "body"), None)
    if body is None:
        return raw_html, 0

    paragraphs = [el for el in body.iter() if _local_name(el.tag) == "p"]
    seen_slugs: set[str] = set()
    injected: list[tuple[CairnFootnote, str, str]] = []

    for footnote in enabled_notes:
        if footnote.entity_slug in seen_slugs:
            continue

        ref_id = make_ref_id(footnote.entity_slug, footnote.chapter_index)
        note_id = make_note_id(footnote.entity_slug, footnote.chapter_index)

        # Prefer the target paragraph_index first, then scan all paragraphs in order
        ordered_targets: list[etree._Element] = []
        if 0 <= footnote.paragraph_index < len(paragraphs):
            ordered_targets.append(paragraphs[footnote.paragraph_index])
        ordered_targets.extend(
            p for idx, p in enumerate(paragraphs) if idx != footnote.paragraph_index
        )
        if not ordered_targets:
            ordered_targets.append(body)

        wrapped = False
        for target_el in ordered_targets:
            if _wrap_first_mention_in_element(
                root,
                target_el,
                footnote.display_name,
                ref_id,
                note_id,
            ):
                wrapped = True
                break

        if wrapped:
            seen_slugs.add(footnote.entity_slug)
            injected.append((footnote, ref_id, note_id))

    if not injected:
        return raw_html, 0

    _ensure_head_and_style(root)
    _append_footnotes_section(root, body, injected)

    serialized = etree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=False,
    ).decode("utf-8")
    return serialized, len(injected)


def inject_footnotes_into_epub(
    input_epub_path: Path | str,
    output_epub_path: Path | str,
    footnotes: Iterable[CairnFootnote],
) -> int:
    """Inject all enabled footnotes across an EPUB archive and write ``output_epub_path``.

    Returns total number of injected anchors across the book.
    """
    out_path = Path(output_epub_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    book = epub.read_epub(str(input_epub_path))
    by_chapter: dict[int, list[CairnFootnote]] = {}
    for fn in footnotes:
        if fn.enabled:
            by_chapter.setdefault(fn.chapter_index, []).append(fn)

    total_injected = 0
    chapter_index = 0

    for spine_entry in book.spine:
        item_id = spine_entry[0] if isinstance(spine_entry, tuple) else spine_entry
        item = book.get_item_with_id(item_id)
        if item is None or isinstance(item, (epub.EpubNav, epub.EpubNcx)):
            continue
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        file_name = item.get_name()
        if file_name.lower() in ("nav.xhtml", "toc.xhtml", "navigation.xhtml"):
            continue

        chapter_notes = by_chapter.get(chapter_index, [])
        if chapter_notes:
            raw_html = item.get_content().decode("utf-8", errors="replace")
            updated_html, count = inject_chapter_footnotes(raw_html, chapter_notes)
            if count > 0:
                item.set_content(updated_html.encode("utf-8"))
                total_injected += count

        chapter_index += 1

    # Guarantee every item in the book and TOC has a non-None string UID for ebooklib's NCX generator
    for idx, item in enumerate(book.get_items()):
        if getattr(item, "uid", None) is None:
            assigned_uid = getattr(item, "id", None) or f"item_{idx}"
            item.uid = str(assigned_uid)
            item.id = str(assigned_uid)

    def _fix_toc_uids(toc_entries: Iterable[Any]) -> None:
        for idx, entry in enumerate(toc_entries):
            if isinstance(entry, (list, tuple)):
                _fix_toc_uids(entry)
            elif hasattr(entry, "uid") and entry.uid is None:
                assigned = (
                    getattr(entry, "id", None)
                    or getattr(entry, "file_name", None)
                    or f"toc_{idx}"
                )
                entry.uid = str(assigned)
                entry.id = str(assigned)

    if hasattr(book, "toc") and book.toc:
        _fix_toc_uids(book.toc)

    # Add E-Ink CSS stylesheet item with explicit string UID & ID
    style_item = epub.EpubItem(
        uid="cairnbooks-eink-css",
        file_name="styles/cairnbooks.css",
        media_type="text/css",
        content=CAIRN_EINK_CSS.encode("utf-8"),
    )
    style_item.id = "cairnbooks-eink-css"
    book.add_item(style_item)

    epub.write_epub(str(out_path), book)
    return total_injected
