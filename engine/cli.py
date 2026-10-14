"""Typer CLI for CairnBooks (`bake`, `inspect`, `convert-kfx`).

Supports `--test-mode` (zero-API deterministic mock execution) and
`--refresh-jev` (cache bypass) as specified in AGENTS.md and PROJECT_SPEC.md.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

# Ensure the repository root is on sys.path when invoked as `python engine/cli.py`
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from engine.config import DEFAULT_MIN_PAGE_GAP
from engine.core.epub_parser import parse_epub
from engine.core.kfx_compiler import compile_epub_to_kfx
from engine.core.lore_ledger import LoreLedger
from engine.core.pipeline import run_bake_pipeline

app = typer.Typer(
    name="cairnbooks",
    help="CairnBooks: Spoiler-free EPUB 3 & Kindle Paperwhite KFX footnote compiler.",
    add_completion=False,
)
console = Console()


@app.command("bake")
def bake_command(
    input_epub: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to the input .epub file.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Optional custom path for the enhanced .epub output.",
        ),
    ] = None,
    gap_pages: Annotated[
        int,
        typer.Option(
            "--gap-pages",
            help="Minimum page absence before an entity qualifies as a reintroduction.",
        ),
    ] = DEFAULT_MIN_PAGE_GAP,
    test_mode: Annotated[
        bool,
        typer.Option(
            "--test-mode",
            help="Use deterministic MockJevClient & MockSynopsisClient with zero external API calls.",
        ),
    ] = False,
    refresh_jev: Annotated[
        bool,
        typer.Option(
            "--refresh-jev",
            help="Bypass persistent DiskCache and force fresh Tier 1 evaluations.",
        ),
    ] = False,
    compile_kfx: Annotated[
        bool,
        typer.Option(
            "--compile-kfx",
            help="Also invoke Calibre ebook-convert to output a Kindle .kfx file.",
        ),
    ] = False,
) -> None:
    """Scan an EPUB, synthesize spoiler-free Cairn footnotes, and bake an enhanced EPUB."""
    mode_label = "TEST-MODE (Mock AI)" if test_mode else "LIVE / FALLBACK"
    console.print(
        f"[bold]CairnBooks Compiler[/bold] • Mode: [cyan]{mode_label}[/cyan] "
        f"• Gap Threshold: [yellow]{gap_pages}p[/yellow]"
    )

    state, kfx_result = run_bake_pipeline(
        input_epub_path=input_epub,
        output_epub_path=output,
        min_page_gap=gap_pages,
        test_mode=test_mode,
        refresh_jev=refresh_jev,
        compile_kfx=compile_kfx,
    )

    table = Table(title=f"Cairn Proof Sheet — {state.book_title} ({state.book_author})")
    table.add_column("Anchor ID", style="cyan", no_wrap=True)
    table.add_column("Entity", style="bold")
    table.add_column("Chapter")
    table.add_column("Absent", justify="right")
    table.add_column("Alignment")
    table.add_column("Synopsis (<= 15 words)")

    for fn in state.footnotes:
        table.add_row(
            fn.anchor_id,
            fn.display_name,
            f"Ch. {fn.chapter_index + 1}",
            f"{fn.pages_absent}p",
            fn.alignment.value.upper(),
            fn.synopsis_text,
        )

    console.print(table)
    console.print(
        f"[green]✔ Baked enhanced EPUB ({len(state.footnotes)} Cairns):[/green] "
        f"{state.output_epub_path}"
    )

    if compile_kfx and kfx_result is not None:
        if kfx_result.success and state.output_kfx_path:
            console.print(
                f"[green]✔ Compiled Kindle KFX:[/green] {state.output_kfx_path}"
            )
        else:
            console.print(
                f"[yellow]⚠ KFX compilation skipped/failed:[/yellow] "
                f"{kfx_result.error_message}"
            )


@app.command("inspect")
def inspect_command(
    input_epub: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to the .epub file to inspect.",
        ),
    ],
    gap_pages: Annotated[
        int,
        typer.Option(
            "--gap-pages",
            help="Minimum page absence threshold for candidate reintroductions.",
        ),
    ] = 0,
) -> None:
    """Inspect parsed chapters, Lore Ledger entities, and candidate reintroductions."""
    book = parse_epub(input_epub)
    ledger = LoreLedger(book)

    console.print(
        f"[bold]{book.title}[/bold] by {book.author} — "
        f"{book.total_chapters} chapters, {book.total_words} words "
        f"(~{book.estimated_pages} pages), {len(ledger.entities)} tracked entities."
    )

    table = Table(title=f"Candidate Reintroductions (gap >= {gap_pages}p)")
    table.add_column("Chapter", style="cyan")
    table.add_column("Entity", style="bold")
    table.add_column("Last Seen")
    table.add_column("Pages Absent", justify="right")

    total_candidates = 0
    for ch in book.chapters:
        for cand in ledger.find_candidate_reintroductions(
            ch.index, min_page_gap=gap_pages
        ):
            total_candidates += 1
            table.add_row(
                f"Ch. {ch.index + 1}: {ch.title}",
                cand.canonical_name,
                f"Ch. {cand.last_seen_chapter_index + 1}",
                str(cand.pages_absent),
            )

    console.print(table)
    console.print(f"Total candidate reintroductions: [bold]{total_candidates}[/bold]")


@app.command("convert-kfx")
def convert_kfx_command(
    input_epub: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to the enhanced .epub file.",
        ),
    ],
    output_kfx: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Optional output .kfx path.",
        ),
    ] = None,
) -> None:
    """Compile an enhanced EPUB 3 file into a Kindle Paperwhite .kfx file via Calibre."""
    result = compile_epub_to_kfx(input_epub, output_kfx)
    if not result.success:
        console.print(f"[red]✖ KFX compilation failed:[/red] {result.error_message}")
        raise typer.Exit(code=1)
    console.print(f"[green]✔ Compiled KFX:[/green] {result.output_path}")


if __name__ == "__main__":
    app()
