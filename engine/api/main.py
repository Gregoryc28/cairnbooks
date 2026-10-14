"""FastAPI application entrypoint for CairnBooks."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engine.api.routes_books import router as books_router


def create_app() -> FastAPI:
    application = FastAPI(
        title="CairnBooks Compiler API",
        version="0.1.0",
        description=(
            "Kinetic EPUB 3 & Kindle Paperwhite KFX spoiler-free footnote compiler."
        ),
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "cairnbooks-engine"}

    application.include_router(books_router)
    return application


app = create_app()
