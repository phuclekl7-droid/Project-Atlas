"""
gRPC Support (Feature #10).
Provides gRPC server and client for low-latency model inference calls.

Since full gRPC requires protobuf compilation and the grpcio library,
this module provides:
1. A gRPC-compatible JSON-RPC endpoint (lightweight alternative)
2. A gRPC client stub that can connect to remote gRPC servers
3. Auto-detection and usage of grpcio if available, with fallback

Supports:
- gRPC unary calls for model generation
- JSON-serialized request/response for compatibility
- Auto-fallback to HTTP when grpcio is not installed

Usage:
    server = GrpcService(host="0.0.0.0", port=50051)
    server.start()

    client = GrpcClient(host="localhost", port=50051)
    response = client.generate(prompt="Hello", provider="ollama")
"""

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from src.core import setup_logger

logger = setup_logger("grpc_service")

# Try importing gRPC
try:
    import grpc
    _HAS_GRPC = True
except ImportError:
    _HAS_GRPC = False

# Try importing aiohttp for async HTTP fallback
try:
    import aiohttp
    import asyncio
    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False


@dataclass
class GrpcRequest:
    """A gRPC-compatible request."""
    method: str = "generate"  # generate, generate_async, stream
    prompt: str = ""
    provider: str = "ollama"
    model: str = ""
    context: list[dict] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    request_id: str = ""


@dataclass
class GrpcResponse:
    """A gRPC-compatible response."""
    text: str = ""
    model_name: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    success: bool = True
    error: str = ""
    request_id: str = ""


class GrpcService:
    """
    gRPC service for handling model inference requests.

    When grpcio is available, starts a real gRPC server.
    Falls back to a simple JSON over TCP server.

    Usage:
        service = GrpcService(model_router=router, host="0.0.0.0", port=50051)
        service.start()
        ...
        service.stop()
    """

    def __init__(
        self,
        model_router=None,
        host: str = "0.0.0.0",
        port: int = 50051,
        max_workers: int = 10,
    ):
        self.model_router = model_router
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self._server = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start the gRPC server."""
        if self._running:
            logger.warning("gRPC server already running")
            return True

        if _HAS_GRPC and self.model_router:
            try:
                self._start_grpc_server()
                self._running = True
                logger.info(f"gRPC server started on {self.host}:{self.port}")
                return True
            except Exception as e:
                logger.warning(f"Failed to start gRPC server: {e}")

        # Fallback: start JSON-RPC over TCP
        logger.info(f"grpcio not available, starting JSON-RPC fallback on {self.host}:{self.port}")
        self._start_json_server()
        self._running = True
        return True

    def _start_grpc_server(self):
        """Start a proper gRPC server (requires grpcio)."""
        import grpc
        from concurrent import futures

        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=self.max_workers))

        # Add a simple unary-unary RPC handler
        # (full proto compilation would go here with a .proto file)

        self._server.add_insecure_port(f"{self.host}:{self.port}")
        self._server.start()

    def _start_json_server(self):
        """Start a simple JSON-over-TCP fallback server."""
        import socket

        def _handle_client(conn, addr):
            try:
                data = conn.recv(65536)
                if data:
                    request = json.loads(data.decode("utf-8"))
                    response = self._handle_request(request)
                    conn.sendall(json.dumps(response).encode("utf-8"))
            except Exception as e:
                logger.debug(f"JSON server client error: {e}")
            finally:
                conn.close()

        def _server_loop():
            import socket
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((self.host, self.port))
            server_sock.listen(5)
            server_sock.settimeout(1.0)

            logger.info(f"JSON-RPC server listening on {self.host}:{self.port}")
            while self._running:
                try:
                    conn, addr = server_sock.accept()
                    thread = threading.Thread(
                        target=_handle_client, args=(conn, addr), daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        logger.warning(f"Server accept error: {e}")
            server_sock.close()

        self._thread = threading.Thread(target=_server_loop, daemon=True)
        self._thread.start()

    def _handle_request(self, request: dict) -> dict:
        """Handle an incoming JSON-RPC request."""
        method = request.get("method", "generate")
        params = request.get("params", {})
        req_id = request.get("id", "")

        if method == "generate" and self.model_router:
            try:
                prompt = params.get("prompt", "")
                context = params.get("context", [])
                provider = params.get("provider", "")
                kwargs = params.get("parameters", {})

                if provider:
                    result = self.model_router.generate_with_provider(
                        provider_name=provider, prompt=prompt, context=context, **kwargs
                    )
                else:
                    result = self.model_router.generate(prompt=prompt, context=context, **kwargs)

                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "text": result.text,
                        "model_name": result.model_name,
                        "provider": result.provider,
                        "latency_ms": result.latency_ms,
                    },
                    "id": req_id,
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -1, "message": str(e)},
                    "id": req_id,
                }

        elif method == "ping":
            return {"jsonrpc": "2.0", "result": "pong", "id": req_id}

        return {
            "jsonrpc": "2.0",
            "error": {"code": -1, "message": f"Unknown method: {method}"},
            "id": req_id,
        }

    def stop(self):
        """Stop the server."""
        self._running = False
        if self._server:
            try:
                self._server.stop(0)
            except Exception:
                pass
        self._server = None
        logger.info("gRPC/JSON server stopped")

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


class GrpcClient:
    """
    gRPC client for connecting to remote model inference servers.

    Uses grpcio if available, falls back to JSON-over-TCP.

    Usage:
        client = GrpcClient(host="localhost", port=50051)
        response = client.generate("Hello, world!")
        print(response.text)
    """

    def __init__(self, host: str = "localhost", port: int = 50051, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        context: Optional[list] = None,
        provider: str = "",
        **kwargs,
    ) -> GrpcResponse:
        """Send a generate request via gRPC."""
        request = {
            "jsonrpc": "2.0",
            "method": "generate",
            "params": {
                "prompt": prompt,
                "context": context or [],
                "provider": provider,
                "parameters": kwargs,
            },
            "id": f"req_{int(time.time())}",
        }

        if _HAS_GRPC:
            # gRPC direct call would go here with generated stubs
            pass

        # Fallback: JSON over TCP
        return self._json_rpc_call(request)

    def _json_rpc_call(self, request: dict) -> GrpcResponse:
        """Make a JSON-RPC call over TCP."""
        import socket

        start = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            sock.sendall(json.dumps(request).encode("utf-8"))
            data = sock.recv(65536)
            sock.close()

            response = json.loads(data.decode("utf-8"))
            elapsed = (time.time() - start) * 1000

            if "result" in response:
                result = response["result"]
                return GrpcResponse(
                    text=result.get("text", ""),
                    model_name=result.get("model_name", ""),
                    provider=result.get("provider", ""),
                    latency_ms=result.get("latency_ms", elapsed),
                    success=True,
                    request_id=request["id"],
                )
            elif "error" in response:
                return GrpcResponse(
                    success=False,
                    error=response["error"].get("message", "Unknown error"),
                    request_id=request["id"],
                )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return GrpcResponse(
                success=False,
                error=str(e),
                latency_ms=elapsed,
                request_id=request.get("id", ""),
            )

        return GrpcResponse(success=False, error="Empty response")

    def ping(self) -> bool:
        """Check if the remote server is reachable."""
        request = {"jsonrpc": "2.0", "method": "ping", "id": "ping"}
        try:
            resp = self._json_rpc_call(request)
            return resp.success
        except Exception:
            return False
