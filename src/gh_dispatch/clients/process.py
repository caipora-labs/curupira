"""Safe asynchronous process execution shared by CLI-specific clients."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from gh_dispatch.errors import CliLaunchError, CliNotFoundError, CliTimeoutError
from gh_dispatch.models import CommandRequest, ProcessResult


class AsyncProcessRunner:
    """Run executables directly, without a shell or command-string parsing."""

    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        capture_streams = request.capture_output or on_stdout_line is not None
        stdout_pipe = asyncio.subprocess.PIPE if capture_streams else None
        stderr_pipe = asyncio.subprocess.PIPE if capture_streams else None

        try:
            process = await asyncio.create_subprocess_exec(
                request.executable,
                *request.arguments,
                cwd=str(request.cwd) if request.cwd is not None else None,
                stdin=None,
                stdout=stdout_pipe,
                stderr=stderr_pipe,
            )
        except FileNotFoundError as error:
            if request.cwd is not None and not request.cwd.is_dir():
                raise CliLaunchError(
                    request.executable,
                    f"working directory does not exist: {request.cwd}",
                ) from error
            raise CliNotFoundError(request.executable) from error
        except OSError as error:
            raise CliLaunchError(request.executable, str(error)) from error

        if on_stdout_line is not None:
            return await self._run_streaming(process, request, on_stdout_line)

        try:
            if request.capture_output:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=request.timeout
                )
                return ProcessResult(
                    returncode=process.returncode or 0,
                    stdout=stdout.decode(errors="replace"),
                    stderr=stderr.decode(errors="replace"),
                )

            if request.timeout is None:
                returncode = await process.wait()
            else:
                returncode = await asyncio.wait_for(process.wait(), timeout=request.timeout)
            return ProcessResult(returncode=returncode)
        except TimeoutError as error:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            timeout = request.timeout or 0.0
            raise CliTimeoutError(request.executable, timeout) from error
        except asyncio.CancelledError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            raise

    async def _run_streaming(
        self,
        process: asyncio.subprocess.Process,
        request: CommandRequest,
        on_stdout_line: Callable[[str], Awaitable[None]],
    ) -> ProcessResult:
        assert process.stdout is not None
        assert process.stderr is not None

        async def collect_stdout() -> bytes:
            chunks: list[bytes] = []
            while line := await process.stdout.readline():
                chunks.append(line)
                await on_stdout_line(line.decode(errors="replace").rstrip("\r\n"))
            return b"".join(chunks)

        stdout_task = asyncio.create_task(collect_stdout())
        stderr_task = asyncio.create_task(process.stderr.read())
        wait_task = asyncio.create_task(process.wait())
        workers = (stdout_task, stderr_task, wait_task)
        try:
            gathered = asyncio.gather(*workers)
            if request.timeout is None:
                stdout, stderr, returncode = await gathered
            else:
                stdout, stderr, returncode = await asyncio.wait_for(gathered, request.timeout)
            return ProcessResult(
                returncode=returncode,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
            )
        except TimeoutError as error:
            self._kill(process)
            await process.wait()
            await asyncio.gather(*workers, return_exceptions=True)
            timeout = request.timeout or 0.0
            raise CliTimeoutError(request.executable, timeout) from error
        except asyncio.CancelledError:
            self._kill(process)
            await process.wait()
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise
        except BaseException:
            self._kill(process)
            await process.wait()
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise

    @staticmethod
    def _kill(process: asyncio.subprocess.Process) -> None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
