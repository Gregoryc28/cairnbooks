"""FastAPI dependencies for CairnBooks API routes.

Provides workspace directory resolvers, test-mode toggles, and optional Clerk
Bearer JWT header extraction so routes can be cleanly overridden in tests.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import Header

from engine.config import JOBS_DIR, OUTPUTS_DIR


def get_jobs_root() -> Path:
    """Return the active directory for per-upload job workspaces."""
    return JOBS_DIR


def get_outputs_root() -> Path:
    """Return the active directory for baked .epub and .kfx artifacts."""
    return OUTPUTS_DIR


def get_default_test_mode() -> bool:
    """Return True when CAIRN_TEST_MODE=1 is set in the environment."""
    return os.getenv("CAIRN_TEST_MODE", "").strip().lower() in ("1", "true", "yes")


def verify_clerk_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    """Extract optional Clerk Bearer token (permissive in local dev/test)."""
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None
