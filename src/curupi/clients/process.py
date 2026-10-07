"""Bounded asynchronous subprocess execution without shell interpretation."""

import asyncio
import logging
import os
import signal
from collections.abc import Awaitable, Callable

from curupi.errors import CliLaunchError, CliNotFoundError, CliTimeoutError
from curupi.models import CommandRequest, ProcessResult

logger = logging.getLogger(__name__)
MAX_EVENT_LINE_BYTES = 1_000_000
READ_CHUNK_BYTES = 16_384


class _OutputBuffer:
    """Retain a bounded output tail while detecting truncation."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.data = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        self.data.extend(chunk)
        excess = len(self.data) - self.limit
        if excess > 0:
            del self.data[:excess]
            self.truncated = True

    def text(self) -> str:
        return self.data.decode(errors="replace")


class AsyncProcessRunner:
    """Run native executables with disconnected stdin and bounded output capture."""

    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        """Reap the process and helper tasks on timeout, cancellation, or callback failure."""
        capture = request.capture_output or on_stdout_line is not None
        try:
            process = await asyncio.create_subprocess_exec(
                request.executable,
                *request.arguments,
                cwd=request.cwd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE if capture else None,
                stderr=asyncio.subprocess.PIPE if capture else None,
                start_new_session=os.name == "posix",
            )
        except OSError as error:
            if request.cwd is not None and not await asyncio.to_thread(request.cwd.is_dir):
                raise CliLaunchError(
                    request.executable, f"working directory does not exist: {request.cwd}"
                ) from error
            if isinstance(error, FileNotFoundError):
                raise CliNotFoundError(request.executable) from error
            raise CliLaunchError(request.executable, str(error)) from error
        stdout = _OutputBuffer(request.max_output_bytes)
        stderr = _OutputBuffer(request.max_output_bytes)
        workers: list[asyncio.Task[object]] = []
        if process.stdout is not None:
            workers.append(
                asyncio.create_task(self._collect(process.stdout, stdout, on_stdout_line))
            )
        if process.stderr is not None:
            workers.append(asyncio.create_task(self._collect(process.stderr, stderr, None)))
        wait = asyncio.create_task(process.wait())
        workers.append(wait)
        try:
            await asyncio.wait_for(asyncio.gather(*workers), timeout=request.timeout)
            return ProcessResult(
                returncode=wait.result(),
                stdout=stdout.text(),
                stderr=stderr.text(),
                output_truncated=stdout.truncated or stderr.truncated,
            )
        except TimeoutError as error:
            await self._cleanup(process, workers)
            raise CliTimeoutError(request.executable, request.timeout or 0.0) from error
        except BaseException:
            await self._cleanup(process, workers)
            raise

    async def _collect(
        self,
        stream: asyncio.StreamReader,
        output: _OutputBuffer,
        callback: Callable[[str], Awaitable[None]] | None,
    ) -> None:
        pending = bytearray()
        discarding = False
        while chunk := await stream.read(READ_CHUNK_BYTES):
            output.append(chunk)
            if callback is None:
                continue
            for fragment in chunk.splitlines(keepends=True):
                ends_line = fragment.endswith(b"\n")
                if not discarding:
                    pending.extend(fragment)
                    if len(pending) > MAX_EVENT_LINE_BYTES:
                        pending.clear()
                        discarding = True
                        logger.warning("Ignoring oversized CLI event line")
                if ends_line:
                    if not discarding:
                        await callback(pending.decode(errors="replace").rstrip("\r\n"))
                    pending.clear()
                    discarding = False
        if callback is not None and pending and not discarding:
            await callback(pending.decode(errors="replace"))

    @staticmethod
    async def _cleanup(
        process: asyncio.subprocess.Process, workers: list[asyncio.Task[object]]
    ) -> None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            elif process.returncode is None:
                process.kill()
        except ProcessLookupError:
            logger.debug("Process already exited during cleanup")
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        await process.wait()
