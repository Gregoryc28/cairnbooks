# AGENTS.md — Operational Rulebook for CairnBooks

## 1. Critical Protocol & Workflow Loop
1. **Mandatory Pre-Flight Read**: Before modifying any file, inspect `PROJECT_SPEC.md` for architectural contracts and read `TASKS.md` to identify the active task marked `[-]`.
2. **Single-Task Atomic Execution**: Work in small, isolated diffs. Execute ONLY the single subtask currently marked `[-]` in `TASKS.md`. Never bundle unrelated refactors or jump ahead to pending `[ ]` tasks.
3. **Prove-Then-Toggle Loop**:
   - Implement the code and accompanying unit/integration test for the active `[-]` task.
   - Run the task's explicit **Verification Criterion** command.
   - Report the terminal output as proof of success.
   - Update `TASKS.md`: change the completed task from `[-]` to `[x]` and advance the next sequential task from `[ ]` to `[-]`.

---

## 2. Commands & Scripts

### Python Backend (`engine/`)
- **Install Dependencies**: `pip install -r engine/requirements.txt`
- **Run Unit & Mock Tests**: `pytest engine/tests/ -v`
- **Lint & Format Check**: `ruff check engine/ && ruff format --check engine/`
- **Type Check**: `mypy engine/`
- **Run CLI (Mock / Zero-API Mode)**: `python engine/cli.py bake engine/tests/fixtures/sample.epub --test-mode`
- **Run CLI (Live Dev Fallback / Bypass Cache)**: `python engine/cli.py bake input.epub --refresh-jev --gap-pages 30`
- **Start FastAPI Dev Server**: `uvicorn engine.api.main:app --reload --host 127.0.0.1 --port 8000`
- **Compile KFX via Calibre CLI**:
  `ebook-convert output.epub output.kfx --output-profile kindle_paperwhite --kfx-output-args="create_kfx_documents=True"`

### Next.js Frontend (`web/`)
- **Install Dependencies**: `npm install --prefix web`
- **Start Dev Server**: `npm run dev --prefix web`
- **Production Build & Type Check**: `npm run build --prefix web && npx --prefix web tsc --noEmit`
- **Lint Frontend**: `npm run lint --prefix web`
- **Run Frontend Tests**: `npm test --prefix web`

---

## 3. Guardrails & Invariants

### Strictly Forbidden Paths
- NEVER read, log, or commit `.env` or `.env.local` files; only update `.env.example` with sanitized placeholders.
- NEVER manually edit cached API responses inside `engine/data/jev_cache/` or `engine/data/ jobs/`.
- NEVER overwrite raw test fixture EPUBs inside `engine/tests/fixtures/`.
- NEVER modify generated Next.js build files inside `web/.next/`.

### Architectural & Domain Invariants
1. **Strict Temporal Spoiler Cutoff (Zero Future Leakage)**:
   - When evaluating or generating a footnote for an entity in Chapter `N`, the Lore Ledger and context slices MUST strictly exclude all chapters `>= N`. Only text from Chapters `1` through `N - 1` may be accessed.
2. **Two-Tier Hybrid AI Routing (Jev + OpenRouter Fallback)**:
   - **Tier 1 (Discriminative Gatekeeper)**: `JevClient` evaluates candidate reintroductions (`is_significant_reintroduction`, `requires_context_refresher`, `current_alignment`). If `JEV_API_KEY` is unset or `AI_PROVIDER_MODE=openrouter_fallback`, route Tier 1 evaluations to OpenRouter using structured JSON outputs and cache every result in `diskcache`.
   - **Tier 2 (Micro-LLM Synopsis)**: Only candidate mentions passing Tier 1 thresholds (`is_significant_reintroduction >= 0.70` OR `requires_context_refresher >= 3`) trigger a Tier 2 call to an OpenRouter free model (`OPENROUTER_SYNOPSIS_MODEL`) to synthesize a `<= 15`-word spoiler-free recap. Never send full chapters to a generative model.
3. **Kindle KFX Native Popup Footnote Markup**:
   - Every injected anchor in an XHTML chapter MUST use bidirectional EPUB 3 semantics so Calibre's KFX compiler generates a bottom-sheet popup card rather than a page-jumping hyperlink:
     - Inline anchor: `<a id="ref-{slug}-ch{N}" href="#note-{slug}-ch{N}" epub:type="noteref" role="doc-noteref" class="cairn-anchor">{Entity}<sup>[?]</sup></a>`
     - Chapter footer aside: `<aside id="note-{slug}-ch{N}" epub:type="footnote" role="doc-footnote">...<a href="#ref-{slug}-ch{N}" role="doc-backlink">&#8617;</a></aside>`
4. **Aesthetic Invariant ("Living Risograph" — Zero Generic AI Slop)**:
   - Forbidden UI patterns: No dark-mode slate/indigo gradients, no glowing neon purple borders, no glassmorphism (`backdrop-blur`), and no generic SaaS Bento grids.
   - Required palette & feel: Warm newsprint background (`#FAF7F0`), Midnight Ink (`#121316`), Fluorescent Risograph Coral (`#FF4C38`), Electric Acid Lime (`#CEFF00`), Washed Halftone Slate (`#E6E2D8`), `2px solid #121316` borders, tactile offset shadows (`4px 4px 0px #121316`), and kinetic text streaming via Cheng Lou's **Pretext** on an HTML5 Canvas.

---

## 4. Verification Gate (Definition of Done)
A task in `TASKS.md` may ONLY be flipped from `[-]` to `[x]` when ALL of the following pass:
1. The specific **Verification Criterion** command listed for that task exits with code `0`.
2. `pytest engine/tests/ -v` passes with 100% green tests (using `MockJevClient` / `MockSynopsisClient` in `--test-mode`).
3. `ruff check engine/` and `npx --prefix web tsc --noEmit` report zero errors.
4. Any modified EPUB output parses cleanly through `lxml.etree` without malformed XML or broken manifest/spine references.
