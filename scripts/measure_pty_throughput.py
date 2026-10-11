"""Measure PtyTerminal throughput and event-loop latency under flood workloads.

Runs three workloads inside Textual ``run_test(size=(120, 40))`` for a fixed
sample window with a 1 ms ticker. Prints machine info and a table of
throughput plus loop latency p50 / p99 / max. Figures are only meaningful on
the machine that executes this script.

Usage (from the repository root):

    uv run --no-sync python scripts/measure_pty_throughput.py
    uv run --no-sync python scripts/measure_pty_throughput.py --seconds 20
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import platform
import tempfile
import time
from pathlib import Path

from textual.app import App, ComposeResult
from typing_extensions import override

from curupira.tui.pty_terminal import PtyTerminal


class _MeasureApp(App[None]):
    """Minimal host that mounts one ``PtyTerminal``."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__()
        self._argv = argv

    @override
    def compose(self) -> ComposeResult:
        yield PtyTerminal(self._argv)


def _percentile(ordered: list[float], fraction: float) -> float:
    """Return a nearest-rank percentile from a sorted sample."""
    if not ordered:
        return float("nan")
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def _cpu_model() -> str:
    """Best-effort CPU model string for the measurement footer."""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def _machine_banner() -> str:
    """Describe the host that produced the numbers."""
    return (
        f"{platform.system()} {platform.release()} "
        f"({platform.machine()}), {_cpu_model()}, "
        f"{os.cpu_count() or '?'} CPUs, Python {platform.python_version()}"
    )


async def _measure_workload(
    argv: list[str],
    *,
    seconds: float,
    size: tuple[int, int],
) -> tuple[float, list[float]]:
    """Run one workload and return ``(bytes_per_second, ticker_gaps)``."""
    fed_bytes = 0
    original_feed = PtyTerminal._feed_bytes_under_budget

    def counting_feed(
        self: PtyTerminal,
        data: bytes | bytearray,
        deadline: float,
    ) -> tuple[int, bool]:
        nonlocal fed_bytes
        fed, budget_hit = original_feed(self, data, deadline)
        fed_bytes += fed
        return fed, budget_hit

    # Monkeypatch for byte accounting only; restored in ``finally``.
    PtyTerminal._feed_bytes_under_budget = counting_feed  # type: ignore[method-assign]
    gaps: list[float] = []
    try:
        app = _MeasureApp(argv)
        async with app.run_test(size=size) as pilot:
            terminal = app.query_one(PtyTerminal)
            for _ in range(200):
                if terminal.pid is not None:
                    break
                await pilot.pause(0.01)
            previous = time.perf_counter()
            deadline = previous + seconds

            async def _ticker() -> None:
                nonlocal previous
                while time.perf_counter() < deadline:
                    await asyncio.sleep(0.001)
                    now = time.perf_counter()
                    gaps.append(now - previous)
                    previous = now

            ticker = asyncio.create_task(_ticker())
            await ticker
            app.exit()
    finally:
        PtyTerminal._feed_bytes_under_budget = original_feed  # type: ignore[method-assign]

    elapsed = seconds
    return fed_bytes / elapsed, gaps


def _format_row(name: str, bytes_per_second: float, gaps: list[float]) -> str:
    """Format one results row."""
    ordered = sorted(gaps)
    p50 = _percentile(ordered, 0.50) * 1000.0
    p99 = _percentile(ordered, 0.99) * 1000.0
    maximum = (ordered[-1] if ordered else float("nan")) * 1000.0
    mb_s = bytes_per_second / 1_000_000.0
    mib_s = bytes_per_second / (1024.0 * 1024.0)
    return (
        f"| `{name}` | {mb_s:.3f} MB/s ({mib_s:.3f} MiB/s) | "
        f"{p50:.1f} ms / {p99:.1f} ms / {maximum:.1f} ms |"
    )


async def _run(seconds: float, size: tuple[int, int]) -> int:
    """Execute the three workloads and print a markdown table."""
    with tempfile.TemporaryDirectory(prefix="curupira-pty-bench-") as tmp:
        blob = Path(tmp) / "forty.bin"
        blob.write_bytes(b"x" * (40 * 1024 * 1024))
        workloads: list[tuple[str, list[str]]] = [
            ("yes | head -c 50000000", ["bash", "-c", "yes | head -c 50000000"]),
            ("seq 2000000", ["bash", "-c", "seq 2000000"]),
            (f"cat {blob.name} (40 MiB)", ["bash", "-c", f"cat '{blob}'"]),
        ]
        print(f"Machine: {_machine_banner()}")
        print(f"Sample: Textual run_test size={size}, {seconds:g} s, 1 ms ticker")
        print()
        print("| Workload | Throughput | Loop latency p50 / p99 / max |")
        print("| --- | --- | --- |")
        for name, argv in workloads:
            rate, gaps = await _measure_workload(argv, seconds=seconds, size=size)
            print(_format_row(name, rate, gaps))
            # Give the previous child a moment to exit before the next fork.
            await asyncio.sleep(0.2)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seconds",
        type=float,
        default=20.0,
        help="Sample window per workload (default: 20)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=120,
        help="run_test width (default: 120)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=40,
        help="run_test height (default: 40)",
    )
    args = parser.parse_args(argv)
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    return asyncio.run(_run(args.seconds, (args.width, args.height)))


if __name__ == "__main__":
    raise SystemExit(main())
