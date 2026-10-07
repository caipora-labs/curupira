"""User-facing errors raised by OpsCli and its CLI clients."""


class DispatchError(Exception):
    """Base class for expected application errors."""


class TransientCliError(DispatchError):
    """A temporary CLI failure that is safe to retry."""


class CliExecutionError(DispatchError):
    """A CLI process exited unsuccessfully."""

    def __init__(self, executable: str, returncode: int, stderr: str) -> None:
        message = f"{executable} exited with status {returncode}"
        if stderr.strip():
            message = f"{message}: {stderr.strip()}"
        super().__init__(message)
        self.executable = executable
        self.returncode = returncode
        self.stderr = stderr


class CliNotFoundError(DispatchError):
    """An external CLI executable could not be found."""

    def __init__(self, executable: str) -> None:
        super().__init__(f"Required executable not found: {executable}")
        self.executable = executable


class CliLaunchError(DispatchError):
    """An executable could not be started with the requested working directory."""

    def __init__(self, executable: str, detail: str) -> None:
        super().__init__(f"could not start {executable}: {detail}")
        self.executable = executable
        self.detail = detail


class CliTimeoutError(TransientCliError):
    """An external CLI did not finish before its timeout."""

    def __init__(self, executable: str, timeout: float) -> None:
        super().__init__(f"{executable} did not finish within {timeout:g} seconds")
        self.executable = executable
        self.timeout = timeout


class CliOutputError(DispatchError):
    """An external CLI returned data that did not match its contract."""


class WorkspacePathError(DispatchError):
    """A workspace destination exists but is not a usable Git checkout."""


class UnsupportedCodingAgentError(DispatchError):
    """No coding-agent adapter is registered for the requested provider."""


class PromptRenderError(DispatchError):
    """A prompt template references invalid or unsupported fields."""


class StateDatabaseError(DispatchError):
    """Local state cannot be read safely; the original file is preserved."""
