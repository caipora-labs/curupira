"""Type stubs for the compiled ``curupira._native`` extension."""

def rust_core_version() -> str:
    """Return the ``curupira-core`` crate version."""

class NativeProcess:
    """A native child process with incrementally readable output pipes."""

    def read_stdout(self) -> bytes | None: ...
    def read_stderr(self) -> bytes | None: ...
    def wait(self) -> int: ...
    def kill(self) -> None: ...

def spawn_process(
    executable: str,
    arguments: tuple[str, ...],
    cwd: str | None,
    capture_output: bool,
) -> NativeProcess:
    """Start a process and return its supervisor handle."""
