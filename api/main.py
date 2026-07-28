"""
Project Atlas — FastAPI Backend API

Decoupled RESTful backend that mirrors the core initialization logic from
app.py's init_backend(). Designed to be consumed by a future Next.js frontend
while the Streamlit UI continues to work unchanged.

Run with:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET  /health                    Health check
    GET  /api/sessions              List all chat sessions
    POST /api/sessions              Create a new session
    GET  /api/sessions/{id}/messages  Get all messages for a session
    POST /api/chat/stream           SSE-stream an AI response
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core import ConfigurationError
from src.knowledge import create_knowledge_base
from src.memory import Memory, Message, Session
from src.model_router import ModelRouter
from src.plugin import PluginLoader
from src.settings import load_settings
from src.workflow import Workflow

logger = logging.getLogger("api")


# ============================================================
# Backend Container (lazy singleton, mirrors app.py init_backend)
# ============================================================


class Backend:
    """
    Lazy-initialized singleton container for core service instances.

    Mirrors the initialization logic of app.py's init_backend() but
    decoupled from Streamlit's session state. Initialized once on
    first access via the get_backend() dependency.
    """

    _instance: Optional["Backend"] = None

    def __init__(self) -> None:
        self.settings = load_settings()
        self.memory = Memory(db_path=self.settings.memory_path)
        self.model_router = ModelRouter(self.settings)
        self.plugin_loader = PluginLoader(plugin_package="src.plugins")
        self.plugin_loader.discover()
        self.knowledge_base = create_knowledge_base(path="data/knowledge")
        self.workflow = Workflow(
            memory=self.memory,
            model_router=self.model_router,
            plugin_loader=self.plugin_loader,
            knowledge_base=self.knowledge_base,
            max_context_messages=self.settings.max_context_messages,
        )

    @classmethod
    def get_instance(cls) -> "Backend":
        """Get or create the singleton Backend instance."""
        if cls._instance is None:
            cls._instance = cls()
            logger.info("Project Atlas API backend initialized")
        return cls._instance

    def shutdown(self) -> None:
        """Gracefully close resources."""
        try:
            self.memory.close()
        except Exception:
            pass


# ── FastAPI Dependency (sync — no await needed) ──

def get_backend() -> Backend:
    """
    FastAPI dependency that provides the singleton Backend instance.

    Usage in endpoints:
        async def list_sessions(deps: Annotated[Backend, Depends(get_backend)]):
            sessions = deps.memory.list_sessions()

    Initialization errors are cached in Backend._init_error so the
    same error surfaces on every request without retrying init.
    """
    return Backend.get_instance()


# ============================================================
# Lifespan — clean shutdown only (init handled by get_backend)
# ============================================================


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Handle startup (no-op — Backend is lazy) and shutdown cleanup."""
    # Startup: nothing to do — Backend.get_instance() is lazy
    yield
    # Shutdown: clean up resources if Backend was ever initialized
    if Backend._instance is not None:
        Backend._instance.shutdown()
        logger.info("Project Atlas API backend shut down.")


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Project Atlas API",
    description="Decoupled backend API for the Personal AI Assistant.",
    version="0.8.0",
    lifespan=_lifespan,
)

# ── CORS: allow any origin (Next.js frontend will connect from a different port) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Pydantic Schemas
# ============================================================


class HealthResponse(BaseModel):
    status: str = "ok"


class SessionSummary(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    message_count: int


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int


class CreateSessionRequest(BaseModel):
    name: Optional[str] = Field(None, description="Optional session name. Auto-generated if omitted.")


class CreateSessionResponse(BaseModel):
    id: str
    name: str
    created_at: str


class MessageItem(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    tokens: int = 0
    provider: Optional[str] = None
    pinned: int = 0
    has_image: bool = False
    image_paths: list[str] = Field(default_factory=list)


class MessageListResponse(BaseModel):
    session_id: str
    messages: list[MessageItem]
    total: int


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Active session ID to stream into")
    prompt: str = Field(..., min_length=1, description="User message text")


# ============================================================
# Helper: Build a Pydantic model from a Memory Session
# ============================================================


def _session_to_summary(s: Session) -> SessionSummary:
    return SessionSummary(
        id=s.id,
        name=s.name,
        created_at=s.created_at,
        updated_at=s.updated_at,
        message_count=s.message_count,
    )


def _message_to_item(m: Message) -> MessageItem:
    return MessageItem(
        id=m.id,
        role=m.role,
        content=m.content,
        created_at=m.created_at,
        tokens=m.tokens,
        provider=m.provider,
        pinned=m.pinned,
        has_image=m.has_image(),
        image_paths=m.image_paths if m.has_image() else [],
    )


# ============================================================
# Endpoints
# ============================================================


@app.get("/health", tags=["System"])
async def health_check() -> HealthResponse:
    """Simple health-check endpoint for monitoring / load-balancer probes."""
    return HealthResponse(status="ok")


@app.get("/api/sessions", tags=["Sessions"])
async def list_sessions(
    deps: Annotated[Backend, Depends(get_backend)],
    limit: int = 100,
    offset: int = 0,
) -> SessionListResponse:
    """
    List all chat sessions, newest first.

    Query parameters:
        limit:  Max sessions to return (default 100, use 0 for all)
        offset: Pagination offset (default 0)
    """
    try:
        if limit == 0:
            limit = 10000  # effectively unlimited
        sessions = deps.memory.list_sessions(limit=limit, offset=offset)
        return SessionListResponse(
            sessions=[_session_to_summary(s) for s in sessions],
            total=len(sessions),
        )
    except Exception as e:
        logger.error("Failed to list sessions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions", tags=["Sessions"], status_code=201)
async def create_session(
    deps: Annotated[Backend, Depends(get_backend)],
    body: CreateSessionRequest,
) -> CreateSessionResponse:
    """
    Create a new chat session.

    Request body:
        name: Optional session name (e.g. "Code Review"). Auto-generated if omitted.
    """
    try:
        session_id = deps.memory.create_session(name=body.name)
        session = deps.memory.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=500, detail="Session created but not found")
        return CreateSessionResponse(
            id=session.id,
            name=session.name,
            created_at=session.created_at,
        )
    except Exception as e:
        logger.error("Failed to create session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/messages", tags=["Messages"])
async def get_session_messages(
    deps: Annotated[Backend, Depends(get_backend)],
    session_id: str,
    limit: int = 100,
    offset: int = 0,
) -> MessageListResponse:
    """
    Get all messages for a session, oldest first.

    Path parameters:
        session_id: The ID of the session

    Query parameters:
        limit:  Max messages to return (default 100, use 0 for all)
        offset: Pagination offset (default 0)
    """
    try:
        memory = deps.memory

        # Verify session exists
        session = memory.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        if limit == 0:
            limit = 10000  # effectively unlimited

        messages = memory.get_messages(session_id, limit=limit, offset=offset)
        total_in_session = memory.count_messages(session_id)

        # Merge pinned messages at the top (deduplicate by id)
        pinned = memory.get_pinned_messages(session_id)
        seen_ids: set[int] = set()
        merged: list[Message] = []
        for m in pinned + messages:
            if m.id not in seen_ids:
                seen_ids.add(m.id)
                merged.append(m)

        return MessageListResponse(
            session_id=session_id,
            messages=[_message_to_item(m) for m in merged],
            total=total_in_session,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get messages for session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# SSE Streaming — Chat endpoint
# ============================================================


async def _stream_chat_tokens(
    backend: Backend,
    session_id: str,
    prompt: str,
) -> AsyncIterator[str]:
    """
    Async generator that wraps workflow.process_stream() and yields
    Server-Sent Events (SSE) formatted strings.

    Each token from the LLM is yielded as:
        data: {token}\n\n

    When streaming completes, yields the terminal event:
        data: [DONE]\n\n

    On error, yields an error event:
        event: error\ndata: {message}\n\n
    """
    try:
        # Verify session exists before streaming
        session = backend.memory.get_session(session_id)
        if session is None:
            yield f"event: error\ndata: Session '{session_id}' not found\n\n"
            return

        # Stream tokens from workflow (use only valid LLM params, not all settings)
        model_kwargs = {
            "temperature": getattr(backend.settings, "temperature", 0.7),
            "top_p": getattr(backend.settings, "top_p", 0.9),
            "max_tokens": getattr(backend.settings, "max_tokens", 2048),
        }
        async for token in backend.workflow.process_stream(
            user_input=prompt,
            session_id=session_id,
            max_context=backend.settings.max_context_messages,
            **model_kwargs,
        ):
            # SSE format: each token is a data event
            safe_token = token.replace("\n", "\\n").replace("\r", "\\r")
            yield f"data: {safe_token}\n\n"

        # Signal completion
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error("Stream error: %s", e)
        yield f"event: error\ndata: {str(e)}\n\n"


@app.post("/api/chat/stream", tags=["Chat"])
async def chat_stream(
    deps: Annotated[Backend, Depends(get_backend)],
    body: ChatRequest,
) -> StreamingResponse:
    """
    Stream an AI response via Server-Sent Events (SSE).

    Accepts a session_id and a prompt. Returns a StreamingResponse
    where each chunk is a SSE `data:` line containing one token.

    Events:
        data: <token>       — One LLM response token
        data: [DONE]         — Streaming completed successfully
        event: error\ndata:...  — An error occurred

    Usage (JavaScript frontend):
        const evtSource = new EventSource("/api/chat/stream");
        // Note: use POST — EventSource only supports GET.
        // Use fetch() with ReadableStream instead:
        fetch("/api/chat/stream", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ session_id: "abc123", prompt: "Hello!" }),
        }).then(res => {
            const reader = res.body.getReader();
            // ... read SSE chunks
        });

    Request body:
        session_id: The chat session to stream into
        prompt: The user's message text

    Returns:
        StreamingResponse with media_type="text/event-stream"
    """
    return StreamingResponse(
        _stream_chat_tokens(deps, body.session_id, body.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )
