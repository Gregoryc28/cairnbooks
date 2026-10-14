# PROJECT_SPEC.md — CairnBooks Technical Specification

## 1. Project Overview & Objectives
**CairnBooks** (`cairnbooks`) is a full-stack kinetic EPUB 3 & Kindle KFX compiler that eliminates reader confusion in dense fiction and non-fiction without risking web-search spoilers. When a reader uploads an `.epub`, CairnBooks indexes every character, faction, and lore term chronologically, uses a discriminative System One evaluator (TypeSafe AI's **Jev**, with an **OpenRouter** development fallback) to pinpoint significant entity reintroductions after long absences, synthesizes strictly spoiler-capped 15-word context briefings via an OpenRouter micro-LLM, and injects native EPUB 3 bidirectional footnote popups ("Cairns") directly into the book's DOM.

### Core Architectural Pillars
1. **Chronological Lore Ledger (Zero-Spoiler Guarantee)**: Deterministic entity extraction per chapter that locks knowledge cutoffs strictly prior to the active chapter (`chapters < N`).
2. **Two-Tier Hybrid AI Pipeline**:
   - **Tier 1 (Discriminative Filter)**: Evaluates candidate scenes (~1,500–2,500 tokens) against typed schemas (`noul`, `score`, `choice`). Uses OpenRouter fallback during the dev stage and switches to the native TypeSafe Jev API (`/evaluate`) in production via config toggle.
   - **Tier 2 (Bounded Micro-LLM Synthesis)**: Invokes a free-tier OpenRouter model only for the ~25–50 approved anchors per book, summarizing strictly prior excerpts into a `<= 15`-word footnote card.
3. **Kindle Paperwhite KFX Popup Compatibility**: Injects W3C/IDPF-compliant `epub:type="noteref"` and `<aside epub:type="footnote">` markup and wraps Calibre's `ebook-convert` CLI to output sideload-ready `.kfx` files.
4. **"Living Risograph" Kinetic Web UI**: Built on Next.js (Vercel), Clerk Auth, DiffUI primitives, and Cheng Lou's **Pretext** canvas engine, which streams book sentences like liquid ink and physically drops anchor pins into place during processing.

---

## 2. Tech Stack & Libraries

### Backend & CLI (`engine/`)
- **Language**: Python 3.11+
- **Web Framework**: `fastapi>=0.110.0`, `uvicorn[standard]>=0.29.0`, `sse-starlette>=2.0.0`, `python-multipart>=0.0.9`
- **EPUB & XML Processing**: `EbookLib>=0.18`, `lxml>=5.1.0`, `beautifulsoup4>=4.12.0`
- **Core Utilities & Caching** (aligned with prior Jev pipeline):
  - `requests>=2.31.0`
  - `pydantic>=2.0.0`
  - `typer[all]>=0.9.0`
  - `rich>=13.0.0`
  - `python-dotenv>=1.0.0`
  - `diskcache>=5.6.0`
  - `pytest>=7.4.0`
- **External CLI Tooling**: Calibre (`ebook-convert`) + KFX Output plugin + Kindle Previewer 3 (for `.kfx` compilation).

### Frontend (`web/`)
- **Framework**: Next.js 15 (App Router, TypeScript 5.x), React 19
- **Deployment**: Vercel
- **Authentication & Billing**: `@clerk/nextjs` (Auth + user metadata credit tracking) + Clerk Webhooks
- **Styling & Components**: Tailwind CSS 3.4+, DiffUI primitives customized to the Risograph broadsheet theme (`Fraunces` display serif + `JetBrains Mono` monospace)
- **Kinetic Typography Engine**: `@chenglou/pretext` (HTML5 Canvas zero-DOM text measurement and streaming layout)

---

## 3. Directory Structure

```text
cairnbooks/
├── AGENTS.md
├── PROJECT_SPEC.md
├── TASKS.md
├── .env.example
├── .gitignore
├── engine/
│   ├── __init__.py
│   ├── config.py                  # Env loader, paths, thresholds, API URLs
│   ├── cli.py                     # Typer CLI (bake, inspect, convert-kfx)
│   ├── conftest.py                # Pytest sys.path bootstrapper
│   ├── requirements.txt           # Python dependencies
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI entrypoint & CORS config
│   │   ├── routes_books.py        # Upload, SSE stream, proof-sheet, bake endpoints
│   │   └── deps.py                # Clerk JWT verifier & job manager dependencies
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── jev_client.py          # Tier 1: Jev API client + OpenRouter structured fallback
│   │   └── synopsis_client.py     # Tier 2: OpenRouter free micro-LLM 15-word summarizer
│   ├── core/
│   │   ├── __init__.py
│   │   ├── epub_parser.py         # Unpacks EPUB spine, extracts clean chapter blocks
│   │   ├── lore_ledger.py         # Tracks entities, chapter gaps, and prior excerpts
│   │   ├── dom_injector.py        # lxml bidirectional noteref/aside XHTML mutator
│   │   ├── kfx_compiler.py        # Subprocess wrapper for Calibre ebook-convert -> .kfx
│   │   └── pipeline.py            # Orchestrates Upload -> Scan -> Proof -> Bake
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic v2 models for Ledger, Jev, Footnotes, SSE
│   ├── data/                      # Git-ignored runtime storage
│   │   ├── jobs/                  # Per-upload unpacked EPUB workspaces
│   │   ├── outputs/               # Compiled .epub and .kfx artifacts
│   │   └── jev_cache/             # diskcache persistent cache directory
│   └── tests/
│       ├── __init__.py
│       ├── mock_clients.py        # Deterministic MockJevClient & MockSynopsisClient
│       ├── test_epub_parser.py
│       ├── test_lore_ledger.py
│       ├── test_jev_client.py
│       ├── test_dom_injector.py
│       └── fixtures/
│           └── sample_novel.epub  # 5-chapter synthetic test EPUB
└── web/
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── next.config.mjs
    └── src/
        ├── middleware.ts          # Clerk auth middleware
        ├── app/
        │   ├── layout.tsx         # Fonts (Fraunces, JetBrains Mono), ClerkProvider
        │   ├── globals.css        # Risograph palette variables & hard-shadow utilities
        │   ├── page.tsx           # 4-Stage Kinetic Compiler Workspace
        │   └── api/webhooks/      # Clerk credit sync routes
        ├── components/
        │   ├── InkDropZone.tsx    # Stage 1: Printing-plate drag-and-drop uploader
        │   ├── PretextCanvas.tsx  # Stage 2: Cheng Lou Pretext fluid text stream + pin drop
        │   ├── SensitivityDial.tsx# Mechanical gap-threshold selector (Conservative/Balanced/Deep)
        │   ├── ProofRibbon.tsx    # Stage 3: Horizontal toggleable card strip of Cairns
        │   ├── KindleModalPreview.tsx # Simulated Paperwhite bottom-sheet footnote popup
        │   └── BakeExporter.tsx   # Stage 4: One-click EPUB 3 & KFX download buttons
        └── lib/
            ├── api.ts             # Typed fetch + EventSource SSE client
            └── types.ts           # Mirrors engine/models/schemas.py
```

---

## 4. Data Models & Schema (`engine/models/schemas.py`)

### 4.1 Lore Ledger & Entity Tracking
```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

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
    chapter_index: int               # 0-based linear spine order
    chapter_title: str
    paragraph_index: int
    char_offset: int
    excerpt: str                     # Verbatim 1-2 sentence context from this chapter
    estimated_page: int              # Calculated at 250 words/page

class LoreEntity(BaseModel):
    slug: str                        # e.g., "high-marshal-vasquez"
    canonical_name: str              # e.g., "Vasquez"
    aliases: list[str] = Field(default_factory=list)
    category: EntityCategory = EntityCategory.CHARACTER
    first_seen_chapter: int
    first_seen_page: int
    mentions: list[EntityMention] = Field(default_factory=list)

class CandidateReintroduction(BaseModel):
    entity_slug: str
    canonical_name: str
    current_chapter_index: int
    current_chapter_title: str
    current_paragraph_index: int
    current_scene_text: str          # ~1,500-2,500 tokens surrounding the mention
    last_seen_chapter_index: int
    pages_absent: int                # Must be >= min_page_gap to qualify
    prior_excerpts: list[str]        # Strictly from chapters < current_chapter_index
```

### 4.2 Tier 1 (Jev Evaluator) & Tier 2 (Synopsis) Contracts
```python
class JevEvaluationResult(BaseModel):
    entity_slug: str
    chapter_index: int
    is_significant_reintroduction: float = Field(ge=0.0, le=1.0) # Jev 'noul' primitive
    requires_context_refresher: int = Field(ge=0, le=5)          # Jev 'score' primitive
    current_alignment: AlignmentChoice                           # Jev 'choice' primitive
    provider_used: str                                           # "jev_native" | "openrouter_fallback" | "mock"
    cached: bool = False

class CairnFootnote(BaseModel):
    anchor_id: str                   # e.g., "cairn-vasquez-ch18"
    entity_slug: str
    display_name: str
    chapter_index: int
    chapter_title: str
    paragraph_index: int
    pages_absent: int
    first_seen_chapter: int
    last_seen_chapter: int
    alignment: AlignmentChoice
    jev_prob: float
    jev_score: int
    synopsis_text: str               # <= 15 words generated strictly from prior_excerpts
    enabled: bool = True             # User can toggle off in Stage 3 Proof Sheet
```

### 4.3 Job State & SSE Stream Events
```python
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
    total_chapters: int
    total_words: int
    estimated_pages: int
    min_page_gap: int = 30
    phase: JobPhase = JobPhase.UPLOADED
    scanned_chapters: int = 0
    entities_tracked: int = 0
    footnotes: list[CairnFootnote] = Field(default_factory=list)
    output_epub_path: Optional[str] = None
    output_kfx_path: Optional[str] = None
    error_message: Optional[str] = None
```

---

## 5. API & Interface Specifications

### 5.1 Backend REST & SSE Endpoints (`engine/api/`)

1. **`POST /api/v1/books/upload`**
   - **Request**: `multipart/form-data` with `file` (`.epub`, max 50MB) and `min_page_gap` (`int`, default `30`).
   - **Response (`201 Created`)**: `BakeJobState` with extracted metadata (`book_title`, `total_chapters`, `total_words`, `estimated_pages`).
   - **Errors**: `400 Bad Request` if not a valid ZIP/EPUB archive or missing `content.opf`.

2. **`GET /api/v1/books/{job_id}/stream`**
   - **Protocol**: `text/event-stream` (Server-Sent Events).
   - **Events Emitted**:
     - `event: sentence_chunk` -> `{"chapter_index": 4, "text": "The ships were led by Vasquez..."}` (drives the Pretext fluid canvas).
     - `event: cairn_dropped` -> Full JSON `CairnFootnote` object when an entity passes Tier 1 + Tier 2.
     - `event: progress` -> `{"scanned_chapters": 12, "total_chapters": 35, "entities_tracked": 184, "anchors_placed": 14}`.
     - `event: complete` -> `{"phase": "PROOF_READY", "total_anchors": 28}`.

3. **`GET /api/v1/books/{job_id}/proof-sheet`**
   - **Response (`200 OK`)**: `BakeJobState` containing the full list of `CairnFootnote` objects for Stage 3 inspection.

4. **`PATCH /api/v1/books/{job_id}/anchors`**
   - **Request Body**: `{"disabled_anchor_ids": ["cairn-szeth-ch12", "cairn-kaladin-ch14"]}`
   - **Response (`200 OK`)**: Updated count of enabled anchors.

5. **`POST /api/v1/books/{job_id}/bake`**
   - **Request Body**: `{"compile_kfx": true}`
   - **Action**: Injects all `enabled == True` `CairnFootnote` nodes into the unpacked XHTML files, writes the CSS rules, repackages the `.epub`, and (if `compile_kfx` is true and Calibre is installed) runs `ebook-convert` to generate `.kfx`.
   - **Response (`200 OK`)**: `{"epub_download_url": "/api/v1/books/{job_id}/download/epub", "kfx_download_url": "/api/v1/books/{job_id}/download/kfx", "kfx_available": true}`.

6. **`GET /api/v1/books/{job_id}/download/{format}`**
   - **Parameters**: `format` in `["epub", "kfx"]`.
   - **Response**: Binary file stream (`application/epub+zip` or `application/octet-stream`).

### 5.2 Tier 1 Jev Client & OpenRouter Fallback Contract (`engine/clients/jev_client.py`)
Following the pattern from your prior project:
- **Primary Mode (`AI_PROVIDER_MODE=jev` and `JEV_API_KEY` present)**:
  POSTs to `{JEV_BASE_URL}/v1/evaluate` with `state` and typed `questions` (`is_significant_reintroduction`: `noul`, `requires_context_refresher`: `score` [0, 5], `current_alignment`: `choice`).
- **Fallback Mode (`AI_PROVIDER_MODE=openrouter_fallback` or missing `JEV_API_KEY`)**:
  POSTs to `{OPENROUTER_BASE_URL}/v1/chat/completions` using `OPENROUTER_FALLBACK_MODEL` with `response_format={"type": "json_object"}` enforcing the exact `JevEvaluationResult` schema.
- **Caching**: SHA-256 hash of `(entity_slug, chapter_index, current_scene_text, schema_version)` stored in `diskcache.Cache(JEV_CACHE_DIR)`. Bypassed when `force_eval=True` (`--refresh-jev`).

---

## 6. Configuration & Environment (`.env.example`)

```ini
# ── AI Provider Routing ───────────────────────────────────
# Set to "openrouter_fallback" during dev; switch to "jev" in production
AI_PROVIDER_MODE=openrouter_fallback

# ── API Keys (NEVER commit real secrets) ──────────────────
JEV_API_KEY=your_typesafe_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# ── Base URLs & Models ────────────────────────────────────
JEV_BASE_URL=https://api.typesafe.ai
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_FALLBACK_MODEL=google/gemini-2.0-flash-exp:free
OPENROUTER_SYNOPSIS_MODEL=google/gemini-2.0-flash-exp:free

# ── Cairn Thresholds & Limits ─────────────────────────────
DEFAULT_MIN_PAGE_GAP=30
JEV_REINTRO_PROB_THRESHOLD=0.70
JEV_REFRESHER_SCORE_MIN=3
MAX_SYNOPSIS_WORDS=15
JEV_REQUEST_DELAY=0.3

# ── Calibre KFX Compiler ──────────────────────────────────
CALIBRE_EBOOK_CONVERT_BIN=ebook-convert

# ── Clerk & Web Frontend (web/.env.local) ─────────────────
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_key_here
CLERK_SECRET_KEY=sk_test_your_clerk_key_here
```
