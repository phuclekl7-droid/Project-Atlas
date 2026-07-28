"""
FastAPI Webhook Server Module (Feature 87)

Provides RESTful API endpoints for external services to interact with Project Atlas.
Supports webhooks from GitHub, custom integrations, and health checks.

Usage:
    from src.webhook_server import start_server, app

    # Start server in background thread
    start_server(port=8765)

    # Or mount in existing FastAPI app
    # app.mount("/atlas", webhook_server.app)
"""

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import queue
import shlex
import subprocess  # nosec: used with caution in hook execution
import uuid
from src.core import setup_logger

# Try to import requests (optional, for hook forwarding)
try:
    import requests as req_lib  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    req_lib = None  # type: ignore
    _HAS_REQUESTS = False

logger = setup_logger("webhook_server")

# Try to import FastAPI (optional dependency)
_HAS_FASTAPI = False
_HAS_UVICORN = False

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
    _HAS_FASTAPI = True
except ImportError:
    FastAPI = None  # type: ignore
    HTTPException = None  # type: ignore

try:
    import uvicorn
    _HAS_UVICORN = True
except ImportError:
    uvicorn = None  # type: ignore


# ============================================================
# Data Models
# ============================================================


@dataclass
class WebhookEvent:
    """Represents an incoming webhook event.

    Attributes:
        source: Source system (e.g., "github", "custom")
        event_type: Event type (e.g., "push", "pull_request")
        payload: Raw event data
        received_at: Timestamp of receipt
        processed: Whether the event was processed
    """

    source: str
    event_type: str
    payload: dict
    received_at: str = ""
    processed: bool = False
    id: int = 0


# ============================================================
# SSE Streaming & Event Hooks (Feature #119)
# ============================================================


@dataclass
class SSEClient:
    """Represents a connected SSE (Server-Sent Events) client.

    Attributes:
        client_id: Unique client identifier
        event_queue: Queue for pushing events to this client
        topics: List of topics the client is subscribed to
        connected_at: When the client connected
    """

    client_id: str
    event_queue: queue.Queue = field(default_factory=queue.Queue)
    topics: list[str] = field(default_factory=lambda: ["*"])
    connected_at: str = ""


@dataclass
class EventHook:
    """An event hook that triggers actions when certain events occur.

    Attributes:
        hook_id: Unique hook identifier
        source: Source to match (e.g., "github", "*")
        event_type: Event type to match (e.g., "push", "*")
        action: Action to perform ("log", "notify", "webhook", "command")
        target: Target URL or command
        enabled: Whether the hook is active
        metadata: Additional hook configuration
    """

    hook_id: str
    source: str = "*"
    event_type: str = "*"
    action: str = "log"
    target: str = ""
    enabled: bool = True
    metadata: dict = field(default_factory=dict)


# ============================================================
# Webhook Server (enhanced with SSE + Event Hooks)
# ============================================================


class WebhookServer:
    """FastAPI-based webhook server with event queuing, SSE streaming, and event hooks.

    Usage:
        server = WebhookServer()
        server.register_handler("github", "push", handle_github_push)
        server.register_hook(EventHook(source="github", event_type="push", action="notify"))
        server.start(port=8765)

        # SSE streaming clients
        client_id = server.subscribe_sse(topics=["github/push", "alerts"])
        # Client connects to GET /sse?client_id=<id>
    """

    def __init__(self):
        self._handlers: dict[str, dict[str, list[callable]]] = {}
        self._events: list[WebhookEvent] = []
        self._event_counter = 0
        self._server_thread: Optional[threading.Thread] = None
        self._uvicorn_server: Any = None

        # SSE and Event Hooks (Feature #119)
        self._sse_clients: dict[str, SSEClient] = {}
        self._event_hooks: list[EventHook] = []
        self._hook_results: list[dict] = []

        if not _HAS_FASTAPI:
            logger.warning("FastAPI not installed. Install with: pip install fastapi uvicorn")
            self._app = None
        else:
            self._app = FastAPI(
                title="Project Atlas Webhook API",
                version="0.7.0",
                description="RESTful API for Project Atlas webhooks and integrations",
            )
            self._setup_routes()

    @property
    def app(self):
        """Get the underlying FastAPI app instance."""
        return self._app

    def register_handler(self, source: str, event_type: str, handler: callable) -> None:
        """Register a handler for a specific source and event type.

        Args:
            source: Source name (e.g., "github", "custom")
            event_type: Event type (e.g., "push", "pull_request", "*")
            handler: Callable that receives the event payload
        """
        if source not in self._handlers:
            self._handlers[source] = {}
        if event_type not in self._handlers[source]:
            self._handlers[source][event_type] = []
        self._handlers[source][event_type].append(handler)
        logger.info(f"Registered handler: {source}/{event_type}")

    # ── SSE Streaming Methods (Feature #119) ──

    def subscribe_sse(self, topics: Optional[list[str]] = None) -> str:
        """Subscribe a new SSE client.

        Args:
            topics: List of topics to subscribe to. ["*"] for all.

        Returns:
            Client ID string
        """
        client_id = str(uuid.uuid4())[:12]
        client = SSEClient(
            client_id=client_id,
            topics=topics or ["*"],
            connected_at=datetime.utcnow().isoformat(),
        )
        self._sse_clients[client_id] = client
        logger.info(f"SSE client {client_id} subscribed to {client.topics}")
        return client_id

    def unsubscribe_sse(self, client_id: str) -> bool:
        """Unsubscribe an SSE client.

        Args:
            client_id: The client ID to remove

        Returns:
            True if removed, False if not found
        """
        return self._sse_clients.pop(client_id, None) is not None

    def _broadcast_to_sse(self, topic: str, data: dict) -> int:
        """Broadcast an event to all subscribed SSE clients.

        Args:
            topic: Event topic
            data: Event data dict

        Returns:
            Number of clients that received the event
        """
        count = 0
        for client in list(self._sse_clients.values()):
            if "*" in client.topics or topic in client.topics:
                try:
                    client.event_queue.put_nowait({
                        "topic": topic,
                        **data,
                    })
                    count += 1
                except queue.Full:
                    logger.warning(f"SSE client {client.client_id} queue full, skipping")
        return count

    # ── Event Hooks Methods (Feature #119) ──

    def register_hook(self, hook: EventHook) -> str:
        """Register an event hook.

        Args:
            hook: EventHook to register

        Returns:
            Hook ID
        """
        if not hook.hook_id:
            hook.hook_id = str(uuid.uuid4())[:8]
        self._event_hooks.append(hook)
        logger.info(f"Registered event hook: {hook.hook_id} ({hook.source}/{hook.event_type} → {hook.action})")
        return hook.hook_id

    def remove_hook(self, hook_id: str) -> bool:
        """Remove an event hook by ID.

        Args:
            hook_id: Hook ID to remove

        Returns:
            True if removed
        """
        for i, h in enumerate(self._event_hooks):
            if h.hook_id == hook_id:
                self._event_hooks.pop(i)
                return True
        return False

    def _execute_hooks(self, source: str, event_type: str, payload: dict) -> list[dict]:
        """Execute registered event hooks for a given event.

        Args:
            source: Event source
            event_type: Event type
            payload: Event payload

        Returns:
            List of hook execution results
        """
        results = []
        for hook in self._event_hooks:
            if not hook.enabled:
                continue
            # Match source and event_type (supports wildcards)
            if hook.source != "*" and hook.source != source:
                continue
            if hook.event_type != "*" and hook.event_type != event_type:
                continue

            result = {
                "hook_id": hook.hook_id,
                "action": hook.action,
                "timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error": None,
            }

            try:
                if hook.action == "log":
                    logger.info(f"[Hook {hook.hook_id}] Event: {source}/{event_type}")
                    result["success"] = True

                elif hook.action == "notify":
                    # Broadcast to SSE clients subscribed to notifications
                    self._broadcast_to_sse(f"notify/{source}", {
                        "type": "notification",
                        "source": source,
                        "event_type": event_type,
                        "summary": payload.get("message", payload.get("action", str(payload)[:100])),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    result["success"] = True

                elif hook.action == "webhook":
                    # Forward to another webhook URL
                    if hook.target and _HAS_REQUESTS:
                        try:
                            resp = req_lib.post(
                                hook.target,
                                json={"source": source, "event": event_type, "payload": payload},
                                timeout=10,
                            )
                            result["status_code"] = resp.status_code
                            result["success"] = 200 <= resp.status_code < 300
                        except Exception as e:
                            result["error"] = f"HTTP forward error: {e}"
                    elif not _HAS_REQUESTS:
                        result["error"] = "requests library not available"

                elif hook.action == "command":
                    # Execute a command (use with caution!)
                    if hook.target:
                        cmd_template = hook.target
                        cmd = cmd_template.format(
                            source=shlex.quote(source),
                            event=shlex.quote(event_type),
                            payload=shlex.quote(json.dumps(payload)[:500]),
                        )
                        try:
                            proc = subprocess.run(
                                cmd, shell=True, capture_output=True, text=True, timeout=30
                            )
                            result["returncode"] = proc.returncode
                            result["stdout"] = proc.stdout[:200]
                            result["success"] = proc.returncode == 0
                        except subprocess.TimeoutExpired:
                            result["error"] = "Command timed out"
                        except Exception as e:
                            result["error"] = str(e)

            except Exception as e:
                result["error"] = str(e)
                logger.error(f"Hook {hook.hook_id} execution error: {e}")

            results.append(result)

        self._hook_results.extend(results)
        self._hook_results = self._hook_results[-100:]  # Keep last 100
        return results

    def _setup_routes(self):
        """Set up FastAPI routes with SSE and Event Hooks support."""
        if not self._app:
            return

        app = self._app

        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/")
        async def root():
            return {
                "service": "Project Atlas Webhook API",
                "version": "0.7.0",
                "endpoints": {
                    "/health": "Health check",
                    "/webhook/github": "GitHub webhook receiver",
                    "/webhook/custom": "Custom webhook receiver",
                    "/events": "Recent events list",
                    "/stats": "Server statistics",
                    "/hooks": "Event hooks management",
                    "/sse": "Server-Sent Events streaming",
                    "/sse/clients": "Connected SSE clients",
                    "/webhook/broadcast": "Broadcast event to all SSE clients",
                },
            }

        @app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "service": "project-atlas-webhook",
                "timestamp": datetime.utcnow().isoformat(),
                "events_received": self._event_counter,
                "registered_sources": list(self._handlers.keys()),
                "sse_clients": len(self._sse_clients),
                "active_hooks": sum(1 for h in self._event_hooks if h.enabled),
            }

        @app.post("/webhook/github")
        async def github_webhook(request: Request):
            """Receive GitHub webhooks."""
            body = await request.body()
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON")

            event_type = request.headers.get("X-GitHub-Event", "push")
            return await self._process_event("github", event_type, payload)

        @app.post("/webhook/custom")
        async def custom_webhook(request: Request):
            """Receive custom webhooks."""
            body = await request.body()
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON")

            event_type = payload.get("event_type", "unknown")
            return await self._process_event("custom", event_type, payload)

        @app.get("/events")
        async def list_events(limit: int = 10):
            """List recent webhook events."""
            events = [
                {
                    "id": e.id,
                    "source": e.source,
                    "event_type": e.event_type,
                    "received_at": e.received_at,
                    "processed": e.processed,
                }
                for e in self._events[-limit:]
            ]
            return {"events": events, "total": len(self._events)}

        @app.get("/stats")
        async def stats():
            """Get server statistics."""
            return {
                "total_events": self._event_counter,
                "events_by_source": self._count_by_source(),
                "registered_handlers": {
                    source: list(types.keys())
                    for source, types in self._handlers.items()
                },
                "sse_clients": len(self._sse_clients),
                "active_hooks": sum(1 for h in self._event_hooks if h.enabled),
                "hook_executions": len(self._hook_results[-100:]),
                "uptime": datetime.utcnow().isoformat(),
            }

        # ── SSE Streaming Endpoint (Feature #119) ──

        @app.get("/sse")
        async def sse_stream(client_id: str = ""):
            """Server-Sent Events streaming endpoint.

            Clients connect with their client_id and receive real-time events.
            If no client_id provided, a new one is created.

            Usage:
                curl -N http://localhost:8765/sse?client_id=my_client
            """
            if not client_id or client_id not in self._sse_clients:
                client_id = self.subscribe_sse(topics=["*"])

            client = self._sse_clients.get(client_id)
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")

            async def event_generator():
                try:
                    while True:
                        try:
                            event_data = client.event_queue.get(timeout=30)
                            yield f"data: {json.dumps(event_data)}\n\n"
                        except queue.Empty:
                            # Send keepalive
                            yield ": keepalive\n\n"
                except asyncio.CancelledError:
                    self._sse_clients.pop(client_id, None)
                    logger.info(f"SSE client {client_id} disconnected")

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        @app.get("/sse/clients")
        async def list_sse_clients():
            """List all connected SSE clients."""
            return {
                "total": len(self._sse_clients),
                "clients": [
                    {
                        "client_id": c.client_id,
                        "topics": c.topics,
                        "connected_at": c.connected_at,
                    }
                    for c in self._sse_clients.values()
                ],
            }

        @app.post("/webhook/broadcast")
        async def broadcast_event(request: Request):
            """Broadcast a custom event to all subscribed SSE clients."""
            body = await request.body()
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON")

            topic = payload.get("topic", "broadcast")
            event_data = {
                "type": "broadcast",
                "topic": topic,
                "data": payload.get("data", {}),
                "timestamp": datetime.utcnow().isoformat(),
            }

            self._broadcast_to_sse(topic, event_data)

            return {
                "status": "broadcast",
                "topic": topic,
                "target_clients": sum(
                    1 for c in self._sse_clients.values()
                    if "*" in c.topics or topic in c.topics
                ),
            }

        # ── Event Hooks Management (Feature #119) ──

        @app.get("/hooks")
        async def list_hooks():
            """List all registered event hooks."""
            return {
                "total": len(self._event_hooks),
                "hooks": [
                    {
                        "hook_id": h.hook_id,
                        "source": h.source,
                        "event_type": h.event_type,
                        "action": h.action,
                        "target": h.target[:100] if h.target else "",
                        "enabled": h.enabled,
                    }
                    for h in self._event_hooks
                ],
            }

        @app.post("/hooks")
        async def create_hook(request: Request):
            """Register a new event hook."""
            body = await request.json()
            hook = EventHook(
                hook_id=str(uuid.uuid4())[:8],
                source=body.get("source", "*"),
                event_type=body.get("event_type", "*"),
                action=body.get("action", "log"),
                target=body.get("target", ""),
                enabled=body.get("enabled", True),
                metadata=body.get("metadata", {}),
            )
            self._event_hooks.append(hook)
            return {
                "status": "created",
                "hook_id": hook.hook_id,
                "hook": hook,
            }

        @app.delete("/hooks/{hook_id}")
        async def delete_hook(hook_id: str):
            """Delete an event hook by ID."""
            for i, h in enumerate(self._event_hooks):
                if h.hook_id == hook_id:
                    self._event_hooks.pop(i)
                    return {"status": "deleted", "hook_id": hook_id}
            raise HTTPException(status_code=404, detail="Hook not found")

        @app.post("/webhook/test")
        async def test_webhook():
            """Generate a test event to verify the webhook pipeline."""
            test_payload = {
                "event_type": "test",
                "message": "This is a test event",
                "timestamp": datetime.utcnow().isoformat(),
            }
            result = await self._process_event("test", "test", test_payload)
            # Also broadcast to SSE
            self._broadcast_to_sse("test", {
                "type": "test",
                "data": test_payload,
                "timestamp": datetime.utcnow().isoformat(),
            })
            return result

    async def _process_event(self, source: str, event_type: str, payload: dict) -> dict:
        """Process an incoming webhook event.

        Args:
            source: Source identifier
            event_type: Event type
            payload: Event data

        Returns:
            Processing result dict
        """
        self._event_counter += 1
        event = WebhookEvent(
            id=self._event_counter,
            source=source,
            event_type=event_type,
            payload=payload,
            received_at=datetime.utcnow().isoformat(),
        )
        self._events.append(event)
        self._events = self._events[-100:]  # Keep last 100 events

        handled = False
        errors = []

        # Dispatch to registered handlers
        source_handlers = self._handlers.get(source, {})
        specific_handlers = source_handlers.get(event_type, [])
        wildcard_handlers = source_handlers.get("*", [])

        for handler in specific_handlers + wildcard_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(payload)
                else:
                    result = handler(payload)
                event.processed = True
                handled = True
                if isinstance(result, dict):
                    logger.info(f"Webhook {source}/{event_type} handled: {result}")
            except Exception as e:
                errors.append(str(e))
                logger.error(f"Webhook handler error: {e}")

        # ── Execute event hooks (Feature #119) ──
        hook_results = self._execute_hooks(source, event_type, payload)

        # ── Broadcast to SSE clients (Feature #119) ──
        self._broadcast_to_sse(f"{source}/{event_type}", {
            "type": "webhook_event",
            "source": source,
            "event_type": event_type,
            "event_id": event.id,
            "timestamp": datetime.utcnow().isoformat(),
            "summary": str(payload)[:200],
        })

        return {
            "status": "processed" if handled else "received",
            "event_id": event.id,
            "source": source,
            "event_type": event_type,
            "handlers_called": len(specific_handlers) + len(wildcard_handlers),
            "hooks_triggered": len(hook_results),
            "errors": errors,
        }

    def _count_by_source(self) -> dict:
        """Count events grouped by source."""
        counts = {}
        for event in self._events:
            counts[event.source] = counts.get(event.source, 0) + 1
        return counts

    def start(self, host: str = "0.0.0.0", port: int = 8765) -> bool:
        """Start the webhook server in a background thread.

        Args:
            host: Host to bind to
            port: Port to listen on

        Returns:
            True if started successfully, False if dependencies missing
        """
        if not _HAS_FASTAPI or not _HAS_UVICORN:
            logger.error(
                "Cannot start webhook server. Install: pip install fastapi uvicorn"
            )
            return False

        if self._server_thread and self._server_thread.is_alive():
            logger.info("Webhook server already running")
            return True

        self._server_thread = threading.Thread(
            target=lambda: uvicorn.run(
                self._app,
                host=host,
                port=port,
                log_level="info",
            ),
            name="webhook-server",
            daemon=True,
        )
        self._server_thread.start()
        logger.info(f"Webhook server started on http://{host}:{port}")
        return True

    def stop(self) -> None:
        """Stop the webhook server."""
        if self._server_thread:
            logger.info("Stopping webhook server...")
            # uvicorn doesn't have a clean stop from another thread,
            # but the daemon thread will exit when the main process exits
            self._server_thread = None


# ============================================================
# Module-level convenience
# ============================================================

_default_server: Optional[WebhookServer] = None


def get_webhook_server() -> WebhookServer:
    """Get or create the default webhook server instance.

    Usage:
        server = get_webhook_server()
        server.register_handler("custom", "*", my_handler)
        server.register_hook(EventHook(source="*", event_type="*", action="notify"))
        server.start(port=8765)
    """
    global _default_server
    if _default_server is None:
        _default_server = WebhookServer()
    return _default_server


def start_server(host: str = "0.0.0.0", port: int = 8765) -> bool:
    """Convenience function to start the webhook server.

    Args:
        host: Host to bind to
        port: Port to listen on

    Returns:
        True if started
    """
    return get_webhook_server().start(host=host, port=port)
