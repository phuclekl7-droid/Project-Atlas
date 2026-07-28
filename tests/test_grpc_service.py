"""
Tests for Feature #10: gRPC Support.
"""

import pytest

from src.core.grpc_service import GrpcService, GrpcClient, GrpcRequest, GrpcResponse


class TestGrpcService:
    def test_start_stop(self):
        service = GrpcService(host="127.0.0.1", port=50061)
        result = service.start()
        assert result is not None
        service.stop()
        assert service._running is False

    def test_address_property(self):
        service = GrpcService(host="0.0.0.0", port=50051)
        assert "50051" in service.address


class TestGrpcClient:
    def test_ping_fail(self):
        client = GrpcClient(host="127.0.0.1", port=50062)
        assert client.ping() is False

    def test_generate_without_server(self):
        client = GrpcClient(host="127.0.0.1", port=50063)
        response = client.generate("test")
        assert not response.success

    def test_grpc_response_fields(self):
        resp = GrpcResponse(text="hello", model_name="test", provider="ollama")
        assert resp.text == "hello"
        assert resp.model_name == "test"

    def test_grpc_response_error(self):
        resp = GrpcResponse(success=False, error="test error")
        assert not resp.success
        assert "error" in resp.error

    def test_grpc_request_defaults(self):
        req = GrpcRequest(prompt="hello")
        assert req.method == "generate"
        assert req.provider == "ollama"

    def test_grpc_request_custom(self):
        req = GrpcRequest(method="stream", prompt="test", provider="openai")
        assert req.method == "stream"
        assert req.provider == "openai"
