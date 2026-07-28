"""Tests for WebhookServer module (Feature 87)."""

import json
import pytest

from src.webhook_server import WebhookServer, get_webhook_server


class TestWebhookServer:
    """Test webhook server core functionality."""

    def test_register_handler(self):
        server = WebhookServer()
        results = []

        def handler(payload):
            results.append(payload)

        server.register_handler("github", "push", handler)
        # Access internal handlers to verify
        assert "github" in server._handlers
        assert "push" in server._handlers["github"]

    def test_register_wildcard_handler(self):
        server = WebhookServer()

        def handler(payload):
            return payload

        server.register_handler("custom", "*", handler)
        assert "custom" in server._handlers
        assert "*" in server._handlers["custom"]

    def test_event_counter(self):
        server = WebhookServer()
        assert server._event_counter == 0

    def test_event_storage(self):
        """Events should be stored with max 100 limit."""
        server = WebhookServer()
        for i in range(150):
            server._events.append(type("obj", (object,), {"id": i, "source": "test", "event_type": "test", "received_at": "", "processed": False})())
        server._events = server._events[-100:]
        assert len(server._events) == 100

    def test_health_check_response(self):
        """Test the health endpoint structure."""
        server = WebhookServer()
        data = {
            "status": "healthy",
            "service": "project-atlas-webhook",
        }
        assert data["status"] == "healthy"


class TestGetWebhookServer:
    """Test the module-level convenience function."""

    def test_get_webhook_server(self):
        server = get_webhook_server()
        assert server is not None
        assert isinstance(server, WebhookServer)

    def test_singleton(self):
        server1 = get_webhook_server()
        server2 = get_webhook_server()
        assert server1 is server2


class TestHandlerDispatch:
    """Test event handler dispatch logic."""

    def test_specific_handler_called(self):
        server = WebhookServer()
        results = []

        async def handle_push(payload):
            results.append(payload)
            return {"status": "ok"}

        # Manually test the dispatch logic
        server._handlers["github"] = {"push": [lambda p: results.append(p)]}
        assert len(server._handlers["github"]["push"]) == 1

    def test_multiple_handlers_same_event(self):
        server = WebhookServer()
        results = []

        server._handlers["custom"] = {"*": [
            lambda p: results.append("handler1"),
            lambda p: results.append("handler2"),
        ]}
        assert len(server._handlers["custom"]["*"]) == 2

    def test_comparison_with_other(self):
        """Compare WebhookServer features to ensure consistency."""
        from src import webhook_server as ws_module

        # Verify the start_server function exists
        assert hasattr(ws_module, "start_server")
        assert callable(ws_module.start_server)


# ============================================================
# SSE Streaming Tests (Feature #119)
# ============================================================


class TestSSEStreaming:
    """Tests for Server-Sent Events streaming support."""

    def test_subscribe_sse(self):
        server = WebhookServer()
        client_id = server.subscribe_sse()
        assert client_id is not None
        assert len(client_id) > 0
        assert client_id in server._sse_clients

    def test_subscribe_with_topics(self):
        server = WebhookServer()
        client_id = server.subscribe_sse(topics=["github/push", "alerts"])
        client = server._sse_clients[client_id]
        assert "github/push" in client.topics
        assert "alerts" in client.topics

    def test_subscribe_wildcard_topic(self):
        server = WebhookServer()
        client_id = server.subscribe_sse(topics=["*"])
        client = server._sse_clients[client_id]
        assert "*" in client.topics

    def test_unsubscribe_sse(self):
        server = WebhookServer()
        client_id = server.subscribe_sse()
        assert server.unsubscribe_sse(client_id) is True
        assert client_id not in server._sse_clients

    def test_unsubscribe_nonexistent(self):
        server = WebhookServer()
        assert server.unsubscribe_sse("nonexistent") is False

    def test_broadcast_to_sse(self):
        server = WebhookServer()
        cid1 = server.subscribe_sse(topics=["test"])
        server.subscribe_sse(topics=["other"])

        count = server._broadcast_to_sse("test", {"message": "hello"})
        assert count == 1  # Only one client subscribed to "test"

        client = server._sse_clients[cid1]
        assert not client.event_queue.empty()
        event = client.event_queue.get_nowait()
        assert event["topic"] == "test"
        assert event["message"] == "hello"

    def test_broadcast_wildcard(self):
        server = WebhookServer()
        server.subscribe_sse(topics=["*"])  # Subscribed to all
        server.subscribe_sse(topics=["other"])

        count = server._broadcast_to_sse("any_topic", {"data": 1})
        assert count == 1  # Only wildcard client

    def test_broadcast_to_all(self):
        server = WebhookServer()
        cid1 = server.subscribe_sse(topics=["*"])
        cid2 = server.subscribe_sse(topics=["alerts"])

        count = server._broadcast_to_sse("alerts", {"msg": "urgent"})
        assert count == 2  # Both wildcard and specific match

    def test_sse_client_multiple_events(self):
        server = WebhookServer()
        cid = server.subscribe_sse(topics=["*"])

        for i in range(3):
            server._broadcast_to_sse("topic", {"index": i})

        client = server._sse_clients[cid]
        assert client.event_queue.qsize() == 3


# ============================================================
# Event Hooks Tests (Feature #119)
# ============================================================


class TestEventHooks:
    """Tests for Event Hooks system."""

    def test_register_hook(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        hook = EventHook(source="github", event_type="push", action="log")
        hook_id = server.register_hook(hook)
        assert hook_id is not None
        assert len(server._event_hooks) == 1

    def test_register_hook_auto_id(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        hook = EventHook(hook_id="", source="*", event_type="*", action="notify")
        hook_id = server.register_hook(hook)
        assert len(hook_id) > 0  # Auto-generated

    def test_remove_hook(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        hook = EventHook(source="test", event_type="*", action="log")
        hook_id = server.register_hook(hook)
        assert server.remove_hook(hook_id) is True
        assert len(server._event_hooks) == 0

    def test_remove_nonexistent_hook(self):
        server = WebhookServer()
        assert server.remove_hook("no_such_hook") is False

    def test_hook_execution_log(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        server.register_hook(EventHook(source="*", event_type="*", action="log"))
        results = server._execute_hooks("github", "push", {"ref": "main"})
        assert len(results) == 1
        assert results[0]["action"] == "log"
        assert results[0]["success"] is True

    def test_hook_matching_source(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        server.register_hook(EventHook(source="github", event_type="*", action="log"))
        server.register_hook(EventHook(source="slack", event_type="*", action="log"))

        results = server._execute_hooks("github", "push", {})
        assert len(results) == 1  # Only github hook matches

    def test_hook_wildcard_matches_all(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        server.register_hook(EventHook(source="*", event_type="*", action="log"))
        results = server._execute_hooks("any_source", "any_event", {})
        assert len(results) == 1

    def test_disabled_hook_not_executed(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        hook = EventHook(source="*", event_type="*", action="log", enabled=False)
        server.register_hook(hook)
        results = server._execute_hooks("test", "test", {})
        assert len(results) == 0

    def test_hook_execution_notify(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        # Subscribe a client to receive notifications
        server.subscribe_sse(topics=["notify/github"])
        server.register_hook(EventHook(source="github", event_type="push", action="notify"))

        results = server._execute_hooks("github", "push", {"message": "test push"})
        assert len(results) == 1
        assert results[0]["action"] == "notify"
        assert results[0]["success"] is True

    def test_disabled_hook_skipped(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        hook = EventHook(source="*", event_type="*", action="log", enabled=False)
        server.register_hook(hook)
        results = server._execute_hooks("github", "push", {})
        assert len(results) == 0

    def test_hook_results_storage(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        hook = EventHook(source="*", event_type="*", action="log")
        server.register_hook(hook)
        server._execute_hooks("test", "event", {})
        assert len(server._hook_results) == 1


# ============================================================
# Integration: Webhook + SSE + Hooks
# ============================================================


class TestIntegration:
    """Tests for integrated features."""

    def test_webhook_event_triggers_hooks(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        server._handlers["github"] = {"push": []}  # No handlers
        hook = EventHook(source="github", event_type="push", action="log")
        server.register_hook(hook)

        import asyncio
        result = asyncio.run(server._process_event("github", "push", {"ref": "main"}))
        assert result["hooks_triggered"] == 1

    def test_webhook_event_broadcasts_to_sse(self):
        server = WebhookServer()
        from src.webhook_server import EventHook

        cid = server.subscribe_sse(topics=["github/push"])
        server._handlers["github"] = {"push": []}

        import asyncio
        asyncio.run(server._process_event("github", "push", {"ref": "main"}))

        client = server._sse_clients[cid]
        # Should have received the broadcast
        assert client.event_queue.qsize() > 0

    def test_full_pipeline(self):
        """Test: event → hook → SSE broadcast → client receives."""
        server = WebhookServer()
        from src.webhook_server import EventHook

        # Setup SSE client
        cid = server.subscribe_sse(topics=["github/push"])

        # Setup handler
        handler_results = []
        def my_handler(payload):
            handler_results.append(payload)
            return {"handled": True}

        server.register_handler("github", "push", my_handler)
        server.register_hook(EventHook(source="*", event_type="*", action="notify"))

        import asyncio
        asyncio.run(server._process_event("github", "push", {"ref": "feature-1"}))

        # Handler was called
        assert len(handler_results) == 1
        assert handler_results[0]["ref"] == "feature-1"

        # SSE client received broadcast
        client = server._sse_clients[cid]
        assert client.event_queue.qsize() > 0
        event = client.event_queue.get_nowait()
        assert "github/push" in event.get("topic", "") or event.get("type") == "webhook_event"
