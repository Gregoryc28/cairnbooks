"""CairnBooks engine configuration.

Loads environment variables (from the repo-root ``.env`` if present), exposes
typed thresholds / API settings, and guarantees runtime data directories exist.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ─────────────────────────────────────────────────
ENGINE_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = ENGINE_DIR.parent

load_dotenv(REPO_ROOT / ".env", override=False)


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value and value.strip() else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        return float(value) if value and value.strip() else default
    except ValueError:
        return default


DATA_DIR: Path = ENGINE_DIR / "data"
JOBS_DIR: Path = DATA_DIR / "jobs"
OUTPUTS_DIR: Path = DATA_DIR / "outputs"
JEV_CACHE_DIR: Path = DATA_DIR / "jev_cache"

for _dir in (JOBS_DIR, OUTPUTS_DIR, JEV_CACHE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ── AI Provider Routing ───────────────────────────────────
JEV_API_KEY: str = _env_str("JEV_API_KEY", "")
OPENROUTER_API_KEY: str = _env_str("OPENROUTER_API_KEY", "")

_requested_mode = _env_str("AI_PROVIDER_MODE", "openrouter_fallback").lower()
# Fall back to OpenRouter whenever the Jev key is missing (AGENTS.md invariant 2).
AI_PROVIDER_MODE: str = (
    "jev" if _requested_mode == "jev" and JEV_API_KEY else "openrouter_fallback"
)

# ── Base URLs & Models ────────────────────────────────────
JEV_BASE_URL: str = _env_str("JEV_BASE_URL", "https://api.typesafe.ai").rstrip("/")
OPENROUTER_BASE_URL: str = _env_str(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")
OPENROUTER_FALLBACK_MODEL: str = _env_str(
    "OPENROUTER_FALLBACK_MODEL", "google/gemini-2.0-flash-exp:free"
)
OPENROUTER_SYNOPSIS_MODEL: str = _env_str(
    "OPENROUTER_SYNOPSIS_MODEL", "google/gemini-2.0-flash-exp:free"
)

# ── Cairn Thresholds & Limits ─────────────────────────────
DEFAULT_MIN_PAGE_GAP: int = _env_int("DEFAULT_MIN_PAGE_GAP", 30)
JEV_REINTRO_PROB_THRESHOLD: float = _env_float("JEV_REINTRO_PROB_THRESHOLD", 0.70)
JEV_REFRESHER_SCORE_MIN: int = _env_int("JEV_REFRESHER_SCORE_MIN", 3)
MAX_SYNOPSIS_WORDS: int = _env_int("MAX_SYNOPSIS_WORDS", 15)
JEV_REQUEST_DELAY: float = _env_float("JEV_REQUEST_DELAY", 0.3)
WORDS_PER_PAGE: int = 250
CACHE_SCHEMA_VERSION: str = "v1"

# ── Calibre KFX Compiler ──────────────────────────────────
CALIBRE_EBOOK_CONVERT_BIN: str = _env_str("CALIBRE_EBOOK_CONVERT_BIN", "ebook-convert")
