"""REST & Server-Sent Events (SSE) endpoints for CairnBooks (PROJECT_SPEC §5.1)."""

from __future__ import annotations

import json
import tempfile
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from engine.api.deps import (
    get_default_test_mode,
    get_jobs_root,
    get_outputs_root,
    verify_clerk_token,
)
from engine.config import DEFAULT_MIN_PAGE_GAP
from engine.core.pipeline import (
    bake_job,
    create_job,
    iter_scan_job,
    load_job_state,
    update_job_anchors,
)
from engine.models.schemas import BakeJobState, JobPhase

router = APIRouter(prefix="/api/v1/books", tags=["books"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


class PatchAnchorsRequest(BaseModel):
    disabled_anchor_ids: list[str] = Field(default_factory=list)


class PatchAnchorsResponse(BaseModel):
    job_id: str
    enabled_anchors: int
    disabled_anchors: int
    total_anchors: int


class BakeRequest(BaseModel):
    compile_kfx: bool = False


class BakeResponse(BaseModel):
    job_id: str
    epub_download_url: str
    kfx_download_url: str | None = None
    kfx_available: bool = False


def _validate_epub_archive(epub_path: Path) -> None:
    """Ensure the uploaded file is a valid ZIP archive containing an OPF package."""
    if not zipfile.is_zipfile(epub_path):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid ZIP/EPUB archive.",
        )
    with zipfile.ZipFile(epub_path, "r") as zf:
        names = zf.namelist()
        has_opf = any(name.lower().endswith(".opf") for name in names)
        has_container = "META-INF/container.xml" in names
        if not (has_opf or has_container):
            raise HTTPException(
                status_code=400,
                detail="Invalid EPUB archive: missing META-INF/container.xml or .opf manifest.",
            )


@router.post("/upload", response_model=BakeJobState, status_code=201)
async def upload_book(
    file: Annotated[UploadFile, File(...)],
    min_page_gap: Annotated[int, Form()] = DEFAULT_MIN_PAGE_GAP,
    jobs_root: Annotated[Path, Depends(get_jobs_root)] = Path(),
    _token: Annotated[str | None, Depends(verify_clerk_token)] = None,
) -> BakeJobState:
    """Upload an `.epub` file, validate its archive structure, and initialize a job."""
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400, detail="Uploaded file exceeds 50MB limit."
        )

    filename = file.filename or "uploaded_book.epub"
    job_id = uuid.uuid4().hex[:12]

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = Path(tmp.name)

    try:
        _validate_epub_archive(tmp_path)
        try:
            state, _ = create_job(
                tmp_path,
                min_page_gap=min_page_gap,
                job_id=job_id,
                filename=filename,
                jobs_root=jobs_root,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse EPUB structure: {exc}",
            ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return state


@router.get("/{job_id}/stream")
async def stream_book_scan(
    job_id: str,
    test_mode: Annotated[bool | None, Query()] = None,
    refresh_jev: Annotated[bool, Query()] = False,
    jobs_root: Annotated[Path, Depends(get_jobs_root)] = Path(),
    default_test_mode: Annotated[bool, Depends(get_default_test_mode)] = False,
) -> EventSourceResponse:
    """Stream real-time scan events (`sentence_chunk`, `cairn_dropped`, `progress`, `complete`)."""
    try:
        state = load_job_state(job_id, jobs_root=jobs_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    effective_test_mode = default_test_mode if test_mode is None else test_mode

    def _event_generator() -> Iterator[dict[str, str]]:
        # If the job was already scanned, replay the cached footnotes and completion state
        if state.phase in (JobPhase.PROOF_READY, JobPhase.COMPLETED):
            for fn in state.footnotes:
                yield {
                    "event": "cairn_dropped",
                    "data": json.dumps(fn.model_dump(mode="json")),
                }
            yield {
                "event": "progress",
                "data": json.dumps(
                    {
                        "scanned_chapters": state.scanned_chapters,
                        "total_chapters": state.total_chapters,
                        "entities_tracked": state.entities_tracked,
                        "anchors_placed": len(state.footnotes),
                    }
                ),
            }
            yield {
                "event": "complete",
                "data": json.dumps(
                    {
                        "phase": state.phase.value,
                        "total_anchors": len(state.footnotes),
                    }
                ),
            }
            return

        for item in iter_scan_job(
            state,
            test_mode=effective_test_mode,
            refresh_jev=refresh_jev,
            jobs_root=jobs_root,
        ):
            yield {
                "event": item.event,
                "data": json.dumps(item.data),
            }

    return EventSourceResponse(_event_generator())


@router.get("/{job_id}/proof-sheet", response_model=BakeJobState)
async def get_proof_sheet(
    job_id: str,
    jobs_root: Annotated[Path, Depends(get_jobs_root)] = Path(),
) -> BakeJobState:
    """Return the current `BakeJobState` and full list of `CairnFootnote` items."""
    try:
        return load_job_state(job_id, jobs_root=jobs_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{job_id}/anchors", response_model=PatchAnchorsResponse)
async def patch_anchors(
    job_id: str,
    payload: PatchAnchorsRequest,
    jobs_root: Annotated[Path, Depends(get_jobs_root)] = Path(),
) -> PatchAnchorsResponse:
    """Disable specified anchor IDs and enable all others for the given job."""
    try:
        updated = update_job_anchors(
            job_id=job_id,
            disabled_anchor_ids=payload.disabled_anchor_ids,
            jobs_root=jobs_root,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    enabled_count = sum(1 for fn in updated.footnotes if fn.enabled)
    total_count = len(updated.footnotes)
    return PatchAnchorsResponse(
        job_id=job_id,
        enabled_anchors=enabled_count,
        disabled_anchors=total_count - enabled_count,
        total_anchors=total_count,
    )


@router.post("/{job_id}/bake", response_model=BakeResponse)
async def bake_book_endpoint(
    job_id: str,
    payload: BakeRequest | None = None,
    jobs_root: Annotated[Path, Depends(get_jobs_root)] = Path(),
    outputs_root: Annotated[Path, Depends(get_outputs_root)] = Path(),
) -> BakeResponse:
    """Inject all enabled footnotes into the EPUB and optionally compile to `.kfx`."""
    try:
        state = load_job_state(job_id, jobs_root=jobs_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    compile_kfx = payload.compile_kfx if payload is not None else False
    baked_state, kfx_result = bake_job(
        state,
        compile_kfx=compile_kfx,
        jobs_root=jobs_root,
        outputs_root=outputs_root,
    )

    kfx_ok = bool(
        kfx_result is not None
        and kfx_result.success
        and baked_state.output_kfx_path
        and Path(baked_state.output_kfx_path).exists()
    )
    return BakeResponse(
        job_id=job_id,
        epub_download_url=f"/api/v1/books/{job_id}/download/epub",
        kfx_download_url=(
            f"/api/v1/books/{job_id}/download/kfx" if kfx_ok else None
        ),
        kfx_available=kfx_ok,
    )


@router.get("/{job_id}/download/{fmt}")
async def download_baked_book(
    job_id: str,
    fmt: Literal["epub", "kfx"],
    jobs_root: Annotated[Path, Depends(get_jobs_root)] = Path(),
) -> FileResponse:
    """Stream the compiled `.epub` or `.kfx` binary artifact."""
    try:
        state = load_job_state(job_id, jobs_root=jobs_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    stem = Path(state.filename).stem
    if fmt == "epub":
        if not state.output_epub_path or not Path(state.output_epub_path).exists():
            raise HTTPException(
                status_code=404,
                detail="Compiled EPUB is not available yet. Call POST /bake first.",
            )
        return FileResponse(
            path=state.output_epub_path,
            media_type="application/epub+zip",
            filename=f"{stem}_cairn.epub",
        )

    if not state.output_kfx_path or not Path(state.output_kfx_path).exists():
        raise HTTPException(
            status_code=404,
            detail="Compiled KFX file is not available for this job.",
        )
    return FileResponse(
        path=state.output_kfx_path,
        media_type="application/octet-stream",
        filename=f"{stem}_cairn.kfx",
    )
