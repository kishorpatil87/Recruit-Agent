"""
FastAPI application — serves the frontend and REST API.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import router
from config.settings import get_settings

settings = get_settings()
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 RecruitAI starting on port {settings.api_port}")
    print(f"   LLM: Ollama Local — {settings.ollama_model}")
    if settings.has_llm:
        print("   ✓ Ollama connected")
    else:
        print(f"   ⚠️  Ollama not reachable at {settings.ollama_base_url}")
        print(f"   1. Install: https://ollama.com/download")
        print(f"   2. Pull model: ollama pull {settings.ollama_model}")
        print(f"   3. Start: ollama serve")
    yield
    print("RecruitAI shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="RecruitAI API",
        version="3.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")

    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_frontend():
            return FileResponse(str(FRONTEND_DIR / "index.html"))

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
