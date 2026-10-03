"""Real local subprocess tests for bounded capture and resource cleanup."""

import asyncio
import sys
from pathlib import Path

import pytest

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.errors import CliLaunchError, CliNotFoundError, CliTimeoutError
from gh_dispatch.models import CommandRequest


async def test_arguments_are_literal_and_stdin_is_disconnected() -> None:
    payload = "data; no shell execution"
    result = await AsyncProcessRunner().run(
        CommandRequest(
            executable=sys.executable,
            arguments=(
                "-c",
                "import sys; print(sys.argv[1]); print(repr(sys.stdin.read()))",
                payload,
            ),
        )
    )
    assert result.returncode == 0
    assert result.stdout == payload + "\n''\n"


async def test_capture_is_bounded_but_callbacks_receive_all_events() -> None:
    lines: list[str] = []

    async def callback(line: str) -> None:
        lines.append(line)

    result = await AsyncProcessRunner().run(
        CommandRequest(
            executable=sys.executable,
            arguments=("-c", "for i in range(1000): print('event-' + str(i))"),
            max_output_bytes=1024,
        ),
        on_stdout_line=callback,
    )
    assert len(lines) == 1000
    assert lines[-1] == "event-999"
    assert len(result.stdout.encode()) <= 1024
    assert result.output_truncated


async def test_oversized_events_do_not_prevent_later_callbacks() -> None:
    lines: list[str] = []

    async def callback(line: str) -> None:
        lines.append(line)

    result = await AsyncProcessRunner().run(
        CommandRequest(
            executable=sys.executable,
            arguments=("-c", "print('x' * 1100000); print('session-event')"),
            max_output_bytes=1024,
        ),
        on_stdout_line=callback,
    )
    assert lines == ["session-event"]
    assert result.returncode == 0


async def test_timeout_terminates_process() -> None:
    with pytest.raises(CliTimeoutError):
        await AsyncProcessRunner().run(
            CommandRequest(
                executable=sys.executable,
                arguments=("-c", "import time; time.sleep(20)"),
                timeout=0.05,
            )
        )


async def test_callback_failure_reaps_process() -> None:
    async def fail(line: str) -> None:
        raise RuntimeError("callback failed")

    with pytest.raises(RuntimeError, match="callback failed"):
        await asyncio.wait_for(
            AsyncProcessRunner().run(
                CommandRequest(
                    executable=sys.executable,
                    arguments=("-c", "import time; print('event', flush=True); time.sleep(20)"),
                ),
                on_stdout_line=fail,
            ),
            2,
        )


async def test_cancellation_reaps_process() -> None:
    started = asyncio.Event()

    async def callback(line: str) -> None:
        started.set()

    running = asyncio.create_task(
        AsyncProcessRunner().run(
            CommandRequest(
                executable=sys.executable,
                arguments=("-c", "import time; print('event', flush=True); time.sleep(20)"),
            ),
            on_stdout_line=callback,
        )
    )
    await asyncio.wait_for(started.wait(), 2)
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(running, 2)


async def test_missing_executable_and_working_directory(tmp_path: Path) -> None:
    with pytest.raises(CliNotFoundError):
        await AsyncProcessRunner().run(CommandRequest(executable="gh-dispatch-not-installed"))
    with pytest.raises(CliLaunchError, match="working directory"):
        await AsyncProcessRunner().run(
            CommandRequest(executable=sys.executable, cwd=tmp_path / "absent")
        )
