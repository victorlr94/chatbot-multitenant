"""Canal web: API FastAPI + widget de chat embebible.

Arranque:
    uv run uvicorn chatbot_app.main:app --reload
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from chatbot_app.bootstrap import AppContext, build_context

_STATIC_DIR = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    refused: bool


def create_app(context: AppContext | None = None) -> FastAPI:
    """Factory de la app. `context` inyectable para tests (con FakeLLM)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.context = context or build_context()
        yield

    app = FastAPI(title="Chatbot multi-tenant", lifespan=lifespan)

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        ctx: AppContext = request.app.state.context
        return {"status": "ok", "tenant": ctx.tenant.id, "model": ctx.settings.llm_model}

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: Request, body: ChatRequest) -> ChatResponse:
        ctx: AppContext = request.app.state.context
        session_id = body.session_id or uuid.uuid4().hex[:12]
        result = ctx.pipeline.handle(session_id, body.message, channel="web")
        return ChatResponse(session_id=session_id, reply=result.reply, refused=result.refused)

    @app.get("/", include_in_schema=False)
    async def widget() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    return app


app = create_app()
