"""Vendored JSON-RPC framing for official extensions (stdout = protocol only)."""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable
from typing import Any

PROTOCOL_VERSION = 1
DEFAULT_MAX_FRAME_BYTES = 16 * 1024 * 1024


def write_frame(payload: bytes) -> None:
    sys.stdout.buffer.write(f"{len(payload):08x}".encode("ascii"))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def read_frame(max_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> bytes:
    header = sys.stdin.buffer.read(8)
    if len(header) < 8:
        raise EOFError("unexpected EOF while reading frame header")
    length = int(header.decode("ascii"), 16)
    if length > max_bytes:
        raise ValueError(f"frame too large: {length}")
    body = sys.stdin.buffer.read(length)
    if len(body) < length:
        raise EOFError("unexpected EOF while reading frame body")
    return body


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


class RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def serve(
    *,
    name: str,
    version: str,
    triggers: list[dict[str, Any]],
    agents: list[dict[str, Any]],
    handlers: dict[str, Callable[[Any], Any]],
) -> None:
    """Serve until EOF or shutdown."""

    def initialize(params: Any) -> dict[str, Any]:
        peer = int((params or {}).get("protocol_version", 0))
        if peer != PROTOCOL_VERSION:
            raise RpcError(-32001, f"incompatible protocol version {peer}")
        return {
            "protocol_version": PROTOCOL_VERSION,
            "server_info": {"name": name, "version": version},
        }

    def describe(_params: Any) -> dict[str, Any]:
        return {"triggers": triggers, "agents": agents}

    def shutdown(_params: Any) -> dict[str, Any]:
        return {}

    dispatch = {
        "initialize": initialize,
        "describe": describe,
        "shutdown": shutdown,
        **handlers,
    }

    while True:
        try:
            raw = read_frame()
        except EOFError:
            return
        request = json.loads(raw.decode("utf-8"))
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params")
        handler = dispatch.get(method)
        if handler is None:
            write_frame(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"method not found: {method}"},
                    }
                ).encode()
            )
            continue
        try:
            result = handler(params)
            write_frame(
                json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode()
            )
            if method == "shutdown":
                return
        except RpcError as exc:
            write_frame(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": exc.code, "message": str(exc)},
                    }
                ).encode()
            )
        except Exception as exc:  # noqa: BLE001
            log(traceback.format_exc())
            write_frame(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32002, "message": f"execution error: {exc}"},
                    }
                ).encode()
            )
