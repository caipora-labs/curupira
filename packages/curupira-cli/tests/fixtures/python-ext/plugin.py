#!/usr/bin/env python3
"""Minimal Python test extension for protocol tests."""

from __future__ import annotations

import json
import sys

PROTOCOL = 2


def write_frame(payload: bytes) -> None:
    sys.stdout.buffer.write(f"{len(payload):08x}".encode("ascii"))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def read_frame() -> bytes:
    header = sys.stdin.buffer.read(8)
    if len(header) < 8:
        raise EOFError
    length = int(header.decode("ascii"), 16)
    return sys.stdin.buffer.read(length)


def main() -> None:
    while True:
        try:
            raw = read_frame()
        except EOFError:
            return
        req = json.loads(raw.decode())
        method = req.get("method")
        req_id = req.get("id")
        if method == "initialize":
            result = {
                "protocol_version": PROTOCOL,
                "server_info": {"name": "python-test-ext", "version": "0.0.1"},
            }
        elif method == "describe":
            result = {
                "triggers": [{"trigger_type": "python-test", "prompt_fields": []}],
                "agents": [],
            }
        elif method == "trigger/validate":
            result = {"ok": True, "configuration": req.get("params", {}).get("configuration")}
        elif method == "trigger/poll":
            result = {"values": None}
        elif method == "shutdown":
            write_frame(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}).encode())
            return
        else:
            write_frame(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"missing {method}"},
                    }
                ).encode()
            )
            continue
        write_frame(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode())


if __name__ == "__main__":
    main()
