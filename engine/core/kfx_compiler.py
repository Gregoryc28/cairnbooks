"""Calibre KFX Compiler Wrapper for CairnBooks.

Wraps Calibre's ``ebook-convert`` CLI to compile enhanced EPUB 3 files into
Kindle Paperwhite ``.kfx`` packages when Calibre and the KFX Output plugin are
installed locally. Gracefully reports unavailability rather than crashing when
``ebook-convert`` is not present on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from engine.config import CALIBRE_EBOOK_CONVERT_BIN


@dataclass(frozen=True)
class KfxCompileResult:
    success: bool
    output_path: Path | None
    command: list[str]
    stdout: str = ""
    stderr: str = ""
    error_message: str | None = None


def resolve_ebook_convert_bin(binary: str = CALIBRE_EBOOK_CONVERT_BIN) -> str | None:
    """Return the resolved path to ``ebook-convert`` if available, else ``None``."""
    candidate = Path(binary)
    if candidate.is_file():
        return str(candidate)
    return shutil.which(binary)


def is_calibre_available(binary: str = CALIBRE_EBOOK_CONVERT_BIN) -> bool:
    """Return ``True`` when Calibre's ``ebook-convert`` CLI is discoverable."""
    return resolve_ebook_convert_bin(binary) is not None


def build_kfx_command(
    input_epub_path: Path | str,
    output_kfx_path: Path | str,
    binary: str = CALIBRE_EBOOK_CONVERT_BIN,
) -> list[str]:
    """Construct the Calibre CLI invocation for Kindle Paperwhite KFX output."""
    return [
        binary,
        str(input_epub_path),
        str(output_kfx_path),
        "--output-profile",
        "kindle_paperwhite",
        "--kfx-output-args=create_kfx_documents=True",
    ]


def compile_epub_to_kfx(
    input_epub_path: Path | str,
    output_kfx_path: Path | str | None = None,
    binary: str = CALIBRE_EBOOK_CONVERT_BIN,
    timeout: float = 300.0,
) -> KfxCompileResult:
    """Compile ``input_epub_path`` to a ``.kfx`` file via ``ebook-convert``."""
    in_path = Path(input_epub_path)
    out_path = (
        Path(output_kfx_path)
        if output_kfx_path is not None
        else in_path.with_suffix(".kfx")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_bin = resolve_ebook_convert_bin(binary)
    if resolved_bin is None:
        cmd = build_kfx_command(in_path, out_path, binary=binary)
        return KfxCompileResult(
            success=False,
            output_path=None,
            command=cmd,
            error_message=(
                f"Calibre binary '{binary}' was not found on PATH. "
                "Install Calibre + KFX Output plugin to enable .kfx compilation."
            ),
        )

    cmd = build_kfx_command(in_path, out_path, binary=resolved_bin)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return KfxCompileResult(
            success=False,
            output_path=None,
            command=cmd,
            error_message=str(exc),
        )

    if proc.returncode != 0 or not out_path.exists():
        err_detail = (
            proc.stderr.strip()
            or proc.stdout.strip()
            or f"Exit code {proc.returncode}"
        )
        return KfxCompileResult(
            success=False,
            output_path=None,
            command=cmd,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error_message=f"ebook-convert failed: {err_detail}",
        )

    return KfxCompileResult(
        success=True,
        output_path=out_path,
        command=cmd,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
