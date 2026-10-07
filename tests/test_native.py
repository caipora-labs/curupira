"""Smoke checks for the compiled opscli-core extension."""

import asyncio
import sys
from collections.abc import Callable

import pytest


def test_rust_core_version_is_non_empty() -> None:
    native = pytest.importorskip("opscli._native")
    version = native.rust_core_version()
    assert isinstance(version, str)
    assert version.strip()


def test_python_wrapper_returns_the_crate_version() -> None:
    native = pytest.importorskip("opscli._native")
    from opscli.native import rust_core_version

    assert rust_core_version() == native.rust_core_version()


async def test_native_process_streams_and_reaps_child() -> None:
    native = pytest.importorskip("opscli._native")
    process = native.spawn_process(
        sys.executable,
        ("-c", "import sys; print('out', flush=True); print('err', file=sys.stderr)"),
        None,
        True,
    )

    async def read_all(read_chunk: Callable[[], bytes | None]) -> bytes:
        chunks: list[bytes] = []
        while chunk := await asyncio.to_thread(read_chunk):
            chunks.append(chunk)
        return b"".join(chunks)

    stdout, stderr = await asyncio.gather(
        read_all(process.read_stdout), read_all(process.read_stderr)
    )
    assert stdout == b"out\n"
    assert stderr == b"err\n"
    assert await asyncio.to_thread(process.wait) == 0
