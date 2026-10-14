### FILE 3: `TASKS.md`

```markdown
# TASKS.md — CairnBooks Implementation Roadmap

## Status Legend
- `[ ]` Pending
- `[-]` In Progress (Active Agent Target)
- `[x]` Completed & Verified

---

## Phase 0: Architecture & Product Decisions (Baseline)
- `[x]` **Task 0.1**: Finalize product name (**CairnBooks**) and core value proposition (automated spoiler-free EPUB 3 / Kindle Paperwhite KFX footnote popups).
- `[x]` **Task 0.2**: Define Two-Tier Hybrid AI pipeline (Tier 1 Jev discriminative filter with OpenRouter dev fallback + Tier 2 OpenRouter free micro-LLM for 15-word synopses).
- `[x]` **Task 0.3**: Lock in "Living Risograph" aesthetic system (`#FAF7F0` newsprint, `#121316` ink, `#FF4C38` coral, `#CEFF00` acid lime, Cheng Lou Pretext canvas) and 4-stage UX flow.

---

## Phase 1: Repository Scaffolding & Configuration
- `[x]` **Task 1.1: Initialize Backend Directory, `config.py`, and `.env.example`**
  - **Action**: Create `engine/` package structure, `engine/requirements.txt`, `engine/conftest.py`, `.env.example`, and `engine/config.py` loading environment variables, thresholds (`JEV_REINTRO_PROB_THRESHOLD = 0.70`, `JEV_REFRESHER_SCORE_MIN = 3`, `DEFAULT_MIN_PAGE_GAP = 30`), and auto-creating `data/jobs`, `data/outputs`, and `data/jev_cache` directories.
  - **Verification Criterion**: Run `python -c "import engine.config as c; assert c.JEV_CACHE_DIR.exists(); print('Config OK')"` and confirm exit code `0`.

- `[x]` **Task 1.2: Define Core Pydantic v2 Schemas (`engine/models/schemas.py`)**
  - **Action**: Implement `AlignmentChoice`, `EntityCategory`, `EntityMention`, `LoreEntity`, `CandidateReintroduction`, `JevEvaluationResult`, `CairnFootnote`, `JobPhase`, and `BakeJobState`.
  - **Verification Criterion**: Run `pytest engine/tests/test_schemas.py -v` verifying validation constraints (e.g., `is_significant_reintroduction` bounded `[0.0, 1.0]`, `requires_context_refresher` bounded `[0, 5]`).

---

## Phase 2: EPUB Parser & Temporal Lore Ledger Engine
- `[x]` **Task 2.1: Create Synthetic Multi-Chapter Test EPUB Fixture & Parser (`engine/core/epub_parser.py`)**
  - **Action**: Write a fixture generator script that creates `engine/tests/fixtures/sample_novel.epub` (5 chapters where characters appear in Ch. 1, vanish for Ch. 2–3, and return in Ch. 4–5). Implement `epub_parser.py` using `ebooklib` and `BeautifulSoup` to extract linear spine chapters, word counts, and paragraph blocks.
  - **Verification Criterion**: Run `pytest engine/tests/test_epub_parser.py -v` and confirm 5 spine chapters and accurate word counts are extracted from `sample_novel.epub`.

- `[-]` **Task 2.2: Implement Chronological Lore Ledger with Strict Spoiler Cutoff (`engine/core/lore_ledger.py`)**
  - **Action**: Build entity extraction and ledger indexing across chapters. Implement `find_candidate_reintroductions(chapter_index, min_page_gap)` ensuring `prior_excerpts` only pulls from `chapter < current_chapter_index`.
  - **Verification Criterion**: Run `pytest engine/tests/test_lore_ledger.py -v` including an explicit unit test asserting that facts from Chapter 5 are never present when querying Chapter 3 or 4.

---

## Phase 3: Tier 1 (Jev + OpenRouter Fallback) & Tier 2 (Synopsis) Clients
- `[ ]` **Task 3.1: Build Tier 1 `JevClient` with OpenRouter Dev Fallback & DiskCache (`engine/clients/jev_client.py`)**
  - **Action**: Implement `JevClient.evaluate_candidate(candidate, force_eval=False)`. Support `AI_PROVIDER_MODE=openrouter_fallback` (JSON schema response) and `AI_PROVIDER_MODE=jev` (native `/v1/evaluate`), backed by `diskcache` in `JEV_CACHE_DIR` and `MockJevClient` for `--test-mode`.
  - **Verification Criterion**: Run `pytest engine/tests/test_jev_client.py -v` verifying mock mode, OpenRouter payload formatting, Jev native payload formatting, and deterministic cache hits.

- `[ ]` **Task 3.2: Build Tier 2 `SynopsisClient` for 15-Word Footnote Generation (`engine/clients/synopsis_client.py`)**
  - **Action**: Implement `SynopsisClient.generate_synopsis(entity_name, prior_excerpts, last_seen_chapter, pages_absent)` calling `OPENROUTER_SYNOPSIS_MODEL` with a strict `<= 15`-word constraint and deterministic fallback template if the API is unreachable.
  - **Verification Criterion**: Run `pytest engine/tests/test_synopsis_client.py -v` confirming word-count enforcement (`<= 15` words) and zero-spoiler prompt construction.

---

## Phase 4: Bidirectional EPUB 3 DOM Injector & Calibre KFX Compiler
- `[ ]` **Task 4.1: Implement Bidirectional EPUB 3 Footnote Injector (`engine/core/dom_injector.py`)**
  - **Action**: Using `lxml.html` / `lxml.etree`, wrap the first mention of each approved entity per chapter in `<a id="ref-..." href="#note-..." epub:type="noteref" role="doc-noteref" class="cairn-anchor">` and append `<section epub:type="footnotes"><aside id="note-..." epub:type="footnote" role="doc-footnote">...<a href="#ref-..." role="doc-backlink">↩</a></aside></section>` plus subtle e-ink CSS.
  - **Verification Criterion**: Run `pytest engine/tests/test_dom_injector.py -v` asserting valid XML output, exact ID/href bidirectional matching, and presence of `epub:type="noteref"` and `epub:type="footnote"`.

- `[ ]` **Task 4.2: Implement Pipeline Orchestrator, KFX Wrapper & Typer CLI (`engine/core/pipeline.py`, `engine/cli.py`)**
  - **Action**: Wire together `epub_parser`, `lore_ledger`, `jev_client`, `synopsis_client`, `dom_injector`, and `kfx_compiler.py` (`ebook-convert`). Expose via `engine/cli.py` with `bake` and `inspect` commands supporting `--test-mode` and `--refresh-jev`.
  - **Verification Criterion**: Run `python engine/cli.py bake engine/tests/fixtures/sample_novel.epub --test-mode` and verify a valid enhanced `.epub` is written to `engine/data/outputs/`.

---

## Phase 5: FastAPI Backend & Real-Time SSE Streaming
- `[ ]` **Task 5.1: Build FastAPI Endpoints & SSE Stream (`engine/api/main.py`, `engine/api/routes_books.py`)**
  - **Action**: Implement `POST /api/v1/books/upload`, `GET /api/v1/books/{job_id}/stream` (SSE emitting `sentence_chunk`, `cairn_dropped`, `progress`, and `complete`), `GET /api/v1/books/{job_id}/proof-sheet`, `PATCH /api/v1/books/{job_id}/anchors`, `POST /api/v1/books/{job_id}/bake`, and `GET /api/v1/books/{job_id}/download/{format}`.
  - **Verification Criterion**: Run `pytest engine/tests/test_api.py -v` using FastAPI `TestClient` to upload `sample_novel.epub`, consume the SSE stream, toggle an anchor off, bake the output, and download the resulting `.epub`.

---

## Phase 6: Next.js "Living Risograph" Frontend & Pretext Canvas
- `[ ]` **Task 6.1: Scaffold Next.js App with Risograph Theme & Clerk Auth (`web/`)**
  - **Action**: Initialize `web/` with Next.js App Router, TypeScript, Tailwind CSS configured with the Risograph palette (`#FAF7F0`, `#121316`, `#FF4C38`, `#CEFF00`, `#E6E2D8`), hard-edge `4px 4px 0px #121316` shadows, `Fraunces` + `JetBrains Mono` typography, and Clerk authentication middleware.
  - **Verification Criterion**: Run `npm run build --prefix web && npx --prefix web tsc --noEmit` with zero errors.

- `[ ]` **Task 6.2: Build Stage 1 (`InkDropZone`) & Stage 2 (`PretextCanvas` + `SensitivityDial`)**
  - **Action**: Implement the printing-press drag-and-drop uploader and the HTML5 Canvas component powered by Cheng Lou's **Pretext** (`@chenglou/pretext`) that streams `sentence_chunk` SSE events across the viewport and drops visual coral/lime pins on `cairn_dropped` events.
  - **Verification Criterion**: Run `npm run build --prefix web` and verify smooth 60fps canvas text layout rendering with mock SSE stream data.

- `[ ]` **Task 6.3: Build Stage 3 (`ProofRibbon` + `KindleModalPreview`) & Stage 4 (`BakeExporter`)**
  - **Action**: Implement the interactive Proof Sheet ribbon allowing users to preview each Cairn inside a simulated Kindle Paperwhite bottom-sheet card, toggle redundant anchors off, and trigger one-click `.epub` / `.kfx` baking and download.
  - **Verification Criterion**: Run `npm run lint --prefix web && npm run build --prefix web` with zero warnings or type errors.

---

## Phase 7: End-to-End Kindle Paperwhite Hardware Verification
- `[ ]` **Task 7.1: Full Dev Bake & KFX Sideload Smoke Test**
  - **Action**: Run a complete book through the web UI using `AI_PROVIDER_MODE=openrouter_fallback`, export the compiled `.kfx`, sideload via USB-C to the Kindle Paperwhite `/documents` directory, and tap an injected `[?]` Cairn anchor.
  - **Verification Criterion**: Confirm the native Kindle bottom-sheet footnote popup card opens inline without navigating away from the active page.
