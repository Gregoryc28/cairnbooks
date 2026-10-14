"""Unit and integration tests for Task 4.2 (Pipeline, KFX Compiler, and Typer CLI)."""

from __future__ import annotations

from pathlib import Path

from lxml import etree  # type: ignore[import-untyped]
from typer.testing import CliRunner

from engine.cli import app
from engine.core.epub_parser import parse_epub
from engine.core.kfx_compiler import build_kfx_command, compile_epub_to_kfx
from engine.core.pipeline import (
    PipelineEvent,
    load_job_state,
    run_bake_pipeline,
    update_job_anchors,
)
from engine.models.schemas import JobPhase

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_EPUB_PATH = FIXTURES_DIR / "sample_novel.epub"
runner = CliRunner()


def test_run_bake_pipeline_test_mode(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    outputs_dir = tmp_path / "outputs"
    events: list[PipelineEvent] = []

    state, kfx_result = run_bake_pipeline(
        SAMPLE_EPUB_PATH,
        test_mode=True,
        on_event=events.append,
        jobs_root=jobs_dir,
        outputs_root=outputs_dir,
    )

    assert kfx_result is None
    assert state.phase is JobPhase.COMPLETED
    assert state.total_chapters == 5
    assert state.scanned_chapters == 5
    assert state.entities_tracked > 0
    assert len(state.footnotes) >= 1
    assert state.output_epub_path is not None

    out_epub = Path(state.output_epub_path)
    assert out_epub.exists()

    # Verify event stream order and types
    event_names = [e.event for e in events]
    assert "sentence_chunk" in event_names
    assert "cairn_dropped" in event_names
    assert "progress" in event_names
    assert event_names[-1] == "complete"

    # Verify persisted job state round-trip
    reloaded = load_job_state(state.job_id, jobs_root=jobs_dir)
    assert reloaded.phase is JobPhase.COMPLETED
    assert len(reloaded.footnotes) == len(state.footnotes)

    # Verify output EPUB chapters parse cleanly with strict lxml XMLParser
    parsed_out = parse_epub(out_epub)
    strict_parser = etree.XMLParser(recover=False)
    for chap in parsed_out.chapters:
        root = etree.fromstring(chap.raw_html.encode("utf-8"), parser=strict_parser)
        assert root is not None


def test_update_job_anchors_toggles_enabled(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    outputs_dir = tmp_path / "outputs"

    state, _ = run_bake_pipeline(
        SAMPLE_EPUB_PATH,
        test_mode=True,
        jobs_root=jobs_dir,
        outputs_root=outputs_dir,
    )
    first_anchor_id = state.footnotes[0].anchor_id

    updated = update_job_anchors(
        state.job_id,
        disabled_anchor_ids=[first_anchor_id],
        jobs_root=jobs_dir,
    )
    by_id = {fn.anchor_id: fn.enabled for fn in updated.footnotes}
    assert by_id[first_anchor_id] is False


def test_kfx_compiler_missing_binary_graceful(tmp_path: Path) -> None:
    out_kfx = tmp_path / "out.kfx"
    cmd = build_kfx_command(SAMPLE_EPUB_PATH, out_kfx, binary="ebook-convert")
    assert "--output-profile" in cmd
    assert "kindle_paperwhite" in cmd

    res = compile_epub_to_kfx(
        SAMPLE_EPUB_PATH,
        out_kfx,
        binary="nonexistent-calibre-binary-xyz",
    )
    assert res.success is False
    assert res.output_path is None
    assert res.error_message is not None
    assert "not found" in res.error_message


def test_cli_bake_and_inspect_commands(tmp_path: Path) -> None:
    custom_out = tmp_path / "cli_baked.epub"
    res_bake = runner.invoke(
        app,
        [
            "bake",
            str(SAMPLE_EPUB_PATH),
            "--test-mode",
            "--output",
            str(custom_out),
        ],
    )
    assert res_bake.exit_code == 0, res_bake.stdout
    assert custom_out.exists()
    assert "Baked enhanced EPUB" in res_bake.stdout

    res_inspect = runner.invoke(
        app,
        [
            "inspect",
            str(SAMPLE_EPUB_PATH),
            "--gap-pages",
            "0",
        ],
    )
    assert res_inspect.exit_code == 0, res_inspect.stdout
    assert "The Siege of Oakhaven" in res_inspect.stdout
