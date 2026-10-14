"""Integration tests for FastAPI Backend & Real-Time SSE Streaming (Task 5.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lxml import etree  # type: ignore[import-untyped]

from engine.api.deps import get_default_test_mode, get_jobs_root, get_outputs_root
from engine.api.main import create_app
from engine.core.epub_parser import parse_epub

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_EPUB_PATH = FIXTURES_DIR / "sample_novel.epub"


def _parse_sse_events(raw_sse: str) -> list[tuple[str, dict[str, object]]]:
    """Parse SSE text stream into a list of (event_name, json_data) tuples."""
    events: list[tuple[str, dict[str, object]]] = []
    current_event = "message"
    data_lines: list[str] = []

    for raw_line in raw_sse.splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            if data_lines:
                payload_str = "\n".join(data_lines)
                events.append((current_event, json.loads(payload_str)))
                current_event = "message"
                data_lines = []
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())

    if data_lines:
        events.append((current_event, json.loads("\n".join(data_lines))))

    return events


@pytest.fixture()
def api_client(tmp_path: Path) -> TestClient:
    jobs_dir = tmp_path / "jobs"
    outputs_dir = tmp_path / "outputs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    app = create_app()
    app.dependency_overrides[get_jobs_root] = lambda: jobs_dir
    app.dependency_overrides[get_outputs_root] = lambda: outputs_dir
    app.dependency_overrides[get_default_test_mode] = lambda: True
    return TestClient(app)


def test_health_endpoint(api_client: TestClient) -> None:
    resp = api_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upload_rejects_invalid_archive(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/v1/books/upload",
        files={"file": ("not_an_epub.epub", b"plain text not a zip", "application/epub+zip")},
        data={"min_page_gap": "30"},
    )
    assert resp.status_code == 400
    assert "not a valid ZIP/EPUB" in resp.json()["detail"]


def test_full_end_to_end_api_lifecycle(api_client: TestClient, tmp_path: Path) -> None:
    # 1. Upload sample_novel.epub
    with SAMPLE_EPUB_PATH.open("rb") as f:
        upload_resp = api_client.post(
            "/api/v1/books/upload",
            files={"file": ("sample_novel.epub", f, "application/epub+zip")},
            data={"min_page_gap": "30"},
        )
    assert upload_resp.status_code == 201, upload_resp.text
    job_data = upload_resp.json()
    job_id = job_data["job_id"]
    assert job_data["book_title"] == "The Siege of Oakhaven"
    assert job_data["book_author"] == "A. R. Sterling"
    assert job_data["total_chapters"] == 5
    assert job_data["phase"] == "UPLOADED"

    # 2. Consume the SSE scan stream
    with api_client.stream("GET", f"/api/v1/books/{job_id}/stream") as stream_resp:
        assert stream_resp.status_code == 200
        raw_sse = "".join(stream_resp.iter_text())

    sse_events = _parse_sse_events(raw_sse)
    event_types = [ev[0] for ev in sse_events]
    assert "sentence_chunk" in event_types
    assert "cairn_dropped" in event_types
    assert "progress" in event_types
    assert event_types[-1] == "complete"

    dropped_cairns = [ev[1] for ev in sse_events if ev[0] == "cairn_dropped"]
    assert len(dropped_cairns) >= 2

    # 3. Inspect proof-sheet
    proof_resp = api_client.get(f"/api/v1/books/{job_id}/proof-sheet")
    assert proof_resp.status_code == 200
    proof_state = proof_resp.json()
    assert proof_state["phase"] == "PROOF_READY"
    footnotes = proof_state["footnotes"]
    assert len(footnotes) == len(dropped_cairns)

    # 4. Toggle the first anchor off via PATCH /anchors
    disabled_id = footnotes[0]["anchor_id"]
    patch_resp = api_client.patch(
        f"/api/v1/books/{job_id}/anchors",
        json={"disabled_anchor_ids": [disabled_id]},
    )
    assert patch_resp.status_code == 200
    patch_body = patch_resp.json()
    assert patch_body["disabled_anchors"] == 1
    assert patch_body["enabled_anchors"] == len(footnotes) - 1

    # 5. Bake the enhanced EPUB
    bake_resp = api_client.post(
        f"/api/v1/books/{job_id}/bake",
        json={"compile_kfx": False},
    )
    assert bake_resp.status_code == 200
    bake_body = bake_resp.json()
    assert bake_body["epub_download_url"] == f"/api/v1/books/{job_id}/download/epub"

    # 6. Download the resulting .epub and verify XML & disabled anchor exclusion
    dl_resp = api_client.get(bake_body["epub_download_url"])
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/epub+zip"

    downloaded_epub = tmp_path / "downloaded_cairn.epub"
    downloaded_epub.write_bytes(dl_resp.content)

    parsed_out = parse_epub(downloaded_epub)
    assert parsed_out.total_chapters == 5

    strict_parser = etree.XMLParser(recover=False)
    combined_html = "\n".join(c.raw_html for c in parsed_out.chapters)
    for chap in parsed_out.chapters:
        etree.fromstring(chap.raw_html.encode("utf-8"), parser=strict_parser)

    # At least one enabled footnote was injected into the DOM
    assert 'epub:type="noteref"' in combined_html
    assert 'epub:type="footnote"' in combined_html
