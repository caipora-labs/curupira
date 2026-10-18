"""JSON-RPC 2.0 extension server loop."""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable
from typing import Any

from .errors import RpcError
from .framing import log, read_frame, write_frame

PROTOCOL_VERSION = 2


class ExtensionServer:
    """Dispatch initialize/describe/trigger/agent methods to callables."""

    def __init__(
        self,
        *,
        name: str,
        version: str,
        triggers: list[dict[str, Any]] | None = None,
        agents: list[dict[str, Any]] | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.triggers = triggers or []
        self.agents = agents or []
        self._handlers: dict[str, Callable[[Any], Any]] = {
            "initialize": self._initialize,
            "describe": self._describe,
            "shutdown": self._shutdown,
        }

    def on(self, method: str, handler: Callable[[Any], Any]) -> None:
        """Register a JSON-RPC method handler."""
        self._handlers[method] = handler

    def _initialize(self, params: Any) -> dict[str, Any]:
        peer = int((params or {}).get("protocol_version", 0))
        if peer != PROTOCOL_VERSION:
            raise RpcError(-32001, f"incompatible protocol version {peer}")
        return {
            "protocol_version": PROTOCOL_VERSION,
            "server_info": {"name": self.name, "version": self.version},
        }

    def _describe(self, _params: Any) -> dict[str, Any]:
        return {"triggers": self.triggers, "agents": self.agents}

    def _shutdown(self, _params: Any) -> dict[str, Any]:
        return {}


def serve_stdio(server: ExtensionServer) -> None:
    """Serve until EOF or shutdown."""
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        try:
            raw = read_frame(stdin)
        except EOFError:
            return
        except Exception as exc:  # noqa: BLE001 — surface parse failures on the wire
            _write_error(stdout, None, -32700, f"parse error: {exc}")
            continue
        try:
            request = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            _write_error(stdout, None, -32700, f"invalid JSON: {exc}")
            continue
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params")
        if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
            _write_error(stdout, req_id, -32600, "invalid request")
            continue
        handler = server._handlers.get(method)
        if handler is None:
            _write_error(stdout, req_id, -32601, f"method not found: {method}")
            continue
        try:
            result = handler(params)
            write_frame(
                stdout,
                json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode("utf-8"),
            )
            if method == "shutdown":
                return
        except RpcError as exc:
            _write_error(stdout, req_id, exc.code, str(exc), exc.data)
        except Exception as exc:  # noqa: BLE001
            log(traceback.format_exc())
            _write_error(stdout, req_id, -32002, f"execution error: {exc}")


def _write_error(stdout: Any, req_id: Any, code: int, message: str, data: Any = None) -> None:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    write_frame(
        stdout,
        json.dumps({"jsonrpc": "2.0", "id": req_id, "error": error}).encode("utf-8"),
    )
