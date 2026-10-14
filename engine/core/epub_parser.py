"""EPUB 3 Parser for CairnBooks.

Unpacks linear spine chapters, extracts clean paragraph blocks, chapter metadata,
and computes word counts and estimated page offsets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ebooklib  # type: ignore[import-untyped]
from bs4 import BeautifulSoup
from ebooklib import epub  # type: ignore[import-untyped]

from engine.config import WORDS_PER_PAGE


@dataclass
class ParsedChapter:
    index: int  # 0-based linear spine index
    title: str
    file_name: str
    paragraphs: list[str] = field(default_factory=list)
    raw_html: str = ""
    word_count: int = 0
    estimated_pages: int = 0


@dataclass
class ParsedBook:
    title: str
    author: str
    chapters: list[ParsedChapter] = field(default_factory=list)
    total_chapters: int = 0
    total_words: int = 0
    estimated_pages: int = 0


def _extract_title(soup: BeautifulSoup, item: Any, chapter_num: int) -> str:
    """Determine chapter title via item.title, heading tags, or fallback."""
    if hasattr(item, "title") and item.title and item.title.strip():
        return item.title.strip()

    heading = soup.find(["h1", "h2", "h3", "h4"])
    if heading and heading.get_text().strip():
        return heading.get_text().strip()

    title_tag = soup.find("title")
    if title_tag and title_tag.get_text().strip():
        return title_tag.get_text().strip()

    return f"Chapter {chapter_num}"


def parse_epub(epub_path: Path | str) -> ParsedBook:
    """Parse an EPUB file into structured linear spine chapters and metadata."""
    book = epub.read_epub(str(epub_path))

    # Extract Dublin Core metadata
    titles = book.get_metadata("DC", "title")
    book_title = titles[0][0] if titles and titles[0] else "Untitled Book"

    creators = book.get_metadata("DC", "creator")
    book_author = creators[0][0] if creators and creators[0] else "Unknown Author"

    parsed_chapters: list[ParsedChapter] = []
    chapter_index = 0

    for spine_entry in book.spine:
        # spine entries are tuples: (item_id, linear_flag) or just item_id
        item_id = spine_entry[0] if isinstance(spine_entry, tuple) else spine_entry
        item = book.get_item_with_id(item_id)

        if item is None:
            continue

        # Skip navigation files, NCX, and non-document items
        if isinstance(item, (epub.EpubNav, epub.EpubNcx)):
            continue

        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        file_name = item.get_name()
        # Heuristic to filter out standalone nav / toc files
        if file_name.lower() in ("nav.xhtml", "toc.xhtml", "navigation.xhtml"):
            continue

        raw_content = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(raw_content, "html.parser")

        title = _extract_title(soup, item, chapter_index + 1)

        # Extract text paragraphs
        paragraphs: list[str] = []
        p_tags = soup.find_all("p")
        if p_tags:
            for p in p_tags:
                text = p.get_text().strip()
                if text:
                    paragraphs.append(text)
        else:
            # Fallback if book uses div or raw body text
            body = soup.find("body")
            if body:
                text = body.get_text().strip()
                if text:
                    paragraphs.append(text)

        # Calculate word counts for this chapter
        full_text = " ".join(paragraphs)
        words = full_text.split()
        word_count = len(words)
        estimated_pages = (
            max(1, math.ceil(word_count / WORDS_PER_PAGE)) if word_count > 0 else 0
        )

        parsed_chapters.append(
            ParsedChapter(
                index=chapter_index,
                title=title,
                file_name=file_name,
                paragraphs=paragraphs,
                raw_html=raw_content,
                word_count=word_count,
                estimated_pages=estimated_pages,
            )
        )
        chapter_index += 1

    total_words = sum(c.word_count for c in parsed_chapters)
    total_estimated_pages = (
        max(1, math.ceil(total_words / WORDS_PER_PAGE)) if total_words > 0 else 0
    )

    return ParsedBook(
        title=book_title,
        author=book_author,
        chapters=parsed_chapters,
        total_chapters=len(parsed_chapters),
        total_words=total_words,
        estimated_pages=total_estimated_pages,
    )
