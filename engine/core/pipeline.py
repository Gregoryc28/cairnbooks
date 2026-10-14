"""End-to-End Pipeline Orchestrator for CairnBooks.

Coordinates the 4-stage lifecycle:
1. ``create_job`` (Upload & Parse EPUB metadata)
2. ``scan_job`` (Chronological Lore Ledger + Tier 1 Jev + Tier 2 Synopsis)
3. ``update_job_anchors`` (Proof Sheet anchor toggling)
4. ``bake_job`` (Bidirectional EPUB 3 DOM injection + optional Calibre KFX compilation)
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from engine.clients.jev_client import JevClient, MockJevClient, passes_jev_threshold
from engine.clients.synopsis_client import MockSynopsisClient, SynopsisClient
from engine.config import DEFAULT_MIN_PAGE_GAP, JOBS_DIR, OUTPUTS_DIR
from engine.core.dom_injector import inject_footnotes_into_epub
from engine.core.epub_parser import ParsedBook, parse_epub
from engine.core.kfx_compiler import KfxCompileResult, compile_epub_to_kfx
from engine.core.lore_ledger import LoreLedger
from engine.models.schemas import (
    BakeJobState,
    CairnFootnote,
    CandidateReintroduction,
    JevEvaluationResult,
    JobPhase,
)


class Tier1Evaluator(Protocol):
    def evaluate_candidate(
        self,
        candidate: CandidateReintroduction,
        force_eval: bool = False,
    ) -> JevEvaluationResult: ...


class Tier2Synthesizer(Protocol):
    def generate_synopsis(
        self,
        entity_name: str,
        prior_excerpts: list[str],
        last_seen_chapter: int,
        pages_absent: int,
    ) -> str: ...


@dataclass(frozen=True)
class PipelineEvent:
    """Structured event emitted during ``iter_scan_job`` (drives CLI & SSE stream)."""

    event: str  # "sentence_chunk" | "cairn_dropped" | "progress" | "complete"
    data: dict[str, Any]


def make_anchor_id(entity_slug: str, chapter_index: int) -> str:
    """Return canonical CairnFootnote anchor ID (1-based chapter label)."""
    return f"cairn-{entity_slug}-ch{chapter_index + 1}"


def get_job_dir(job_id: str, jobs_root: Path = JOBS_DIR) -> Path:
    return jobs_root / job_id


def get_job_state_path(job_id: str, jobs_root: Path = JOBS_DIR) -> Path:
    return get_job_dir(job_id, jobs_root=jobs_root) / "state.json"


def get_job_source_epub_path(job_id: str, jobs_root: Path = JOBS_DIR) -> Path:
    return get_job_dir(job_id, jobs_root=jobs_root) / "source.epub"


def save_job_state(state: BakeJobState, jobs_root: Path = JOBS_DIR) -> Path:
    """Persist ``BakeJobState`` to ``engine/data/jobs/{job_id}/state.json``."""
    job_dir = get_job_dir(state.job_id, jobs_root=jobs_root)
    job_dir.mkdir(parents=True, exist_ok=True)
    state_path = get_job_state_path(state.job_id, jobs_root=jobs_root)
    state_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return state_path


def load_job_state(job_id: str, jobs_root: Path = JOBS_DIR) -> BakeJobState:
    """Load a persisted ``BakeJobState`` from disk."""
    state_path = get_job_state_path(job_id, jobs_root=jobs_root)
    if not state_path.exists():
        raise FileNotFoundError(f"Job state not found for job_id={job_id!r}")
    return BakeJobState.model_validate_json(state_path.read_text(encoding="utf-8"))


def create_job(
    epub_path: Path | str,
    min_page_gap: int = DEFAULT_MIN_PAGE_GAP,
    job_id: str | None = None,
    filename: str | None = None,
    jobs_root: Path = JOBS_DIR,
) -> tuple[BakeJobState, ParsedBook]:
    """Initialize a new job workspace, copy source EPUB, and parse book metadata."""
    src_path = Path(epub_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Input EPUB not found: {src_path}")

    resolved_job_id = job_id or uuid.uuid4().hex[:12]
    job_dir = get_job_dir(resolved_job_id, jobs_root=jobs_root)
    job_dir.mkdir(parents=True, exist_ok=True)

    dest_epub = get_job_source_epub_path(resolved_job_id, jobs_root=jobs_root)
    if src_path.resolve() != dest_epub.resolve():
        shutil.copy2(src_path, dest_epub)

    parsed_book = parse_epub(dest_epub)
    state = BakeJobState(
        job_id=resolved_job_id,
        filename=filename or src_path.name,
        book_title=parsed_book.title,
        book_author=parsed_book.author,
        total_chapters=parsed_book.total_chapters,
        total_words=parsed_book.total_words,
        estimated_pages=parsed_book.estimated_pages,
        min_page_gap=min_page_gap,
        phase=JobPhase.UPLOADED,
    )
    save_job_state(state, jobs_root=jobs_root)
    return state, parsed_book


def iter_scan_job(
    state: BakeJobState,
    parsed_book: ParsedBook | None = None,
    *,
    test_mode: bool = False,
    refresh_jev: bool = False,
    jev_client: Tier1Evaluator | None = None,
    synopsis_client: Tier2Synthesizer | None = None,
    jobs_root: Path = JOBS_DIR,
) -> Iterator[PipelineEvent]:
    """Generator scanning chapters chronologically and yielding ``PipelineEvent`` items."""
    book = parsed_book or parse_epub(
        get_job_source_epub_path(state.job_id, jobs_root=jobs_root)
    )
    ledger = LoreLedger(book)

    owns_jev_client = False
    if jev_client is None:
        if test_mode:
            jev_client = MockJevClient()
        else:
            jev_client = JevClient()
            owns_jev_client = True

    if synopsis_client is None:
        synopsis_client = MockSynopsisClient() if test_mode else SynopsisClient()

    # In --test-mode on synthetic short fixtures (< min_page_gap total pages),
    # allow page_gap=0 when the book itself is shorter than min_page_gap so mock
    # runs still exercise candidate evaluation and DOM footnote injection.
    effective_page_gap = state.min_page_gap
    if test_mode and book.estimated_pages < state.min_page_gap:
        effective_page_gap = 0

    state.phase = JobPhase.SCANNING
    state.scanned_chapters = 0
    state.entities_tracked = len(ledger.entities)
    state.footnotes = []
    save_job_state(state, jobs_root=jobs_root)

    try:
        for chapter in book.chapters:
            # Emit representative sentence chunks for the kinetic Pretext stream
            for paragraph in chapter.paragraphs[:2]:
                snippet = paragraph.strip()
                if snippet:
                    yield PipelineEvent(
                        event="sentence_chunk",
                        data={
                            "chapter_index": chapter.index,
                            "chapter_title": chapter.title,
                            "text": snippet,
                        },
                    )

            candidates = ledger.find_candidate_reintroductions(
                chapter.index,
                min_page_gap=effective_page_gap,
            )

            for candidate in candidates:
                eval_result = jev_client.evaluate_candidate(
                    candidate,
                    force_eval=refresh_jev,
                )
                if not passes_jev_threshold(eval_result):
                    continue

                synopsis = synopsis_client.generate_synopsis(
                    entity_name=candidate.canonical_name,
                    prior_excerpts=candidate.prior_excerpts,
                    last_seen_chapter=candidate.last_seen_chapter_index,
                    pages_absent=candidate.pages_absent,
                )
                entity = ledger.get_entity(candidate.entity_slug)
                first_seen_ch = (
                    entity.first_seen_chapter
                    if entity is not None
                    else candidate.last_seen_chapter_index
                )

                footnote = CairnFootnote(
                    anchor_id=make_anchor_id(
                        candidate.entity_slug,
                        candidate.current_chapter_index,
                    ),
                    entity_slug=candidate.entity_slug,
                    display_name=candidate.canonical_name,
                    chapter_index=candidate.current_chapter_index,
                    chapter_title=candidate.current_chapter_title,
                    paragraph_index=candidate.current_paragraph_index,
                    pages_absent=candidate.pages_absent,
                    first_seen_chapter=first_seen_ch,
                    last_seen_chapter=candidate.last_seen_chapter_index,
                    alignment=eval_result.current_alignment,
                    jev_prob=eval_result.is_significant_reintroduction,
                    jev_score=eval_result.requires_context_refresher,
                    synopsis_text=synopsis,
                    enabled=True,
                )
                state.footnotes.append(footnote)
                yield PipelineEvent(
                    event="cairn_dropped",
                    data=footnote.model_dump(mode="json"),
                )

            state.scanned_chapters = chapter.index + 1
            save_job_state(state, jobs_root=jobs_root)
            yield PipelineEvent(
                event="progress",
                data={
                    "scanned_chapters": state.scanned_chapters,
                    "total_chapters": state.total_chapters,
                    "entities_tracked": state.entities_tracked,
                    "anchors_placed": len(state.footnotes),
                },
            )

        state.phase = JobPhase.PROOF_READY
        save_job_state(state, jobs_root=jobs_root)
        yield PipelineEvent(
            event="complete",
            data={
                "phase": state.phase.value,
                "total_anchors": len(state.footnotes),
            },
        )
    except Exception as exc:
        state.phase = JobPhase.ERROR
        state.error_message = str(exc)
        save_job_state(state, jobs_root=jobs_root)
        raise
    finally:
        if owns_jev_client and isinstance(jev_client, JevClient):
            jev_client.close()


def scan_job(
    state: BakeJobState,
    parsed_book: ParsedBook | None = None,
    *,
    test_mode: bool = False,
    refresh_jev: bool = False,
    jev_client: Tier1Evaluator | None = None,
    synopsis_client: Tier2Synthesizer | None = None,
    on_event: Callable[[PipelineEvent], None] | None = None,
    jobs_root: Path = JOBS_DIR,
) -> BakeJobState:
    """Run ``iter_scan_job`` to completion and return the updated ``BakeJobState``."""
    for event in iter_scan_job(
        state,
        parsed_book=parsed_book,
        test_mode=test_mode,
        refresh_jev=refresh_jev,
        jev_client=jev_client,
        synopsis_client=synopsis_client,
        jobs_root=jobs_root,
    ):
        if on_event is not None:
            on_event(event)
    return state


def update_job_anchors(
    job_id: str,
    disabled_anchor_ids: list[str],
    jobs_root: Path = JOBS_DIR,
) -> BakeJobState:
    """Toggle ``enabled`` on a job's footnotes given the list of disabled anchor IDs."""
    state = load_job_state(job_id, jobs_root=jobs_root)
    disabled_set = set(disabled_anchor_ids)
    for footnote in state.footnotes:
        footnote.enabled = footnote.anchor_id not in disabled_set
    save_job_state(state, jobs_root=jobs_root)
    return state


def bake_job(
    state: BakeJobState,
    *,
    output_epub_path: Path | str | None = None,
    compile_kfx: bool = False,
    jobs_root: Path = JOBS_DIR,
    outputs_root: Path = OUTPUTS_DIR,
) -> tuple[BakeJobState, KfxCompileResult | None]:
    """Inject enabled footnotes into the EPUB and optionally compile to ``.kfx``."""
    state.phase = JobPhase.BAKING
    save_job_state(state, jobs_root=jobs_root)

    outputs_root.mkdir(parents=True, exist_ok=True)
    stem = Path(state.filename).stem
    if output_epub_path is not None:
        resolved_epub_out = Path(output_epub_path)
    else:
        resolved_epub_out = outputs_root / f"{stem}_cairn_{state.job_id}.epub"

    source_epub = get_job_source_epub_path(state.job_id, jobs_root=jobs_root)
    inject_footnotes_into_epub(source_epub, resolved_epub_out, state.footnotes)
    state.output_epub_path = str(resolved_epub_out.resolve())

    kfx_result: KfxCompileResult | None = None
    if compile_kfx:
        kfx_target = resolved_epub_out.with_suffix(".kfx")
        kfx_result = compile_epub_to_kfx(resolved_epub_out, kfx_target)
        if kfx_result.success and kfx_result.output_path is not None:
            state.output_kfx_path = str(kfx_result.output_path.resolve())

    state.phase = JobPhase.COMPLETED
    save_job_state(state, jobs_root=jobs_root)
    return state, kfx_result


def run_bake_pipeline(
    input_epub_path: Path | str,
    *,
    output_epub_path: Path | str | None = None,
    min_page_gap: int = DEFAULT_MIN_PAGE_GAP,
    test_mode: bool = False,
    refresh_jev: bool = False,
    compile_kfx: bool = False,
    on_event: Callable[[PipelineEvent], None] | None = None,
    jobs_root: Path = JOBS_DIR,
    outputs_root: Path = OUTPUTS_DIR,
) -> tuple[BakeJobState, KfxCompileResult | None]:
    """Execute the full Create -> Scan -> Bake pipeline in one call."""
    state, parsed_book = create_job(
        input_epub_path,
        min_page_gap=min_page_gap,
        jobs_root=jobs_root,
    )
    scan_job(
        state,
        parsed_book=parsed_book,
        test_mode=test_mode,
        refresh_jev=refresh_jev,
        on_event=on_event,
        jobs_root=jobs_root,
    )
    return bake_job(
        state,
        output_epub_path=output_epub_path,
        compile_kfx=compile_kfx,
        jobs_root=jobs_root,
        outputs_root=outputs_root,
    )
