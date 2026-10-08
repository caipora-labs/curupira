"""Validated requests and results for subprocess execution."""

from pathlib import Path

from pydantic import Field, StrictBool

from curupira.models.base import NonEmptyString, OutputLimit, PositiveSeconds, ValidatedModel
from curupira.models.profiles import CliProfile, OpenCodeCliProfile
from curupira.models.tasks import Task


class CodingTaskRequest(ValidatedModel):
    """A native CLI invocation with validated provider options.

    Attributes:
        cwd: Working directory of the coding-agent process.
        message: Prompt sent to the coding agent.
        profile: Provider-specific CLI options.
        session_id: Optional native session to resume.
        timeout: Optional time limit, in seconds.
        max_output_bytes: Maximum captured output per stream.
    """

    cwd: Path
    message: NonEmptyString
    profile: CliProfile = Field(default_factory=OpenCodeCliProfile)
    session_id: NonEmptyString | None = None
    timeout: PositiveSeconds | None = None
    max_output_bytes: OutputLimit = 1_000_000


class CommandRequest(ValidatedModel):
    """An argument vector executed directly, never through a shell.

    Attributes:
        executable: Executable name resolved on ``PATH`` or an explicit path.
        arguments: Arguments passed verbatim, without shell interpretation.
        cwd: Optional working directory.
        timeout: Optional time limit, in seconds.
        capture_output: Whether stdout and stderr are captured.
        max_output_bytes: Maximum captured output per stream.
    """

    executable: NonEmptyString
    arguments: tuple[str, ...] = ()
    cwd: Path | None = None
    timeout: PositiveSeconds | None = 30.0
    capture_output: StrictBool = True
    max_output_bytes: OutputLimit = 1_000_000


class ProcessResult(ValidatedModel):
    """A process exit status and bounded text output.

    Attributes:
        returncode: Process exit status.
        stdout: Captured standard output.
        stderr: Captured standard error.
        output_truncated: Whether either stream exceeded ``max_output_bytes``.
    """

    returncode: int
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False


class DispatchOutcome(ValidatedModel):
    """The selected task and optional process result from one-shot dispatch.

    Attributes:
        selected: Task chosen for dispatch, or ``None`` when nothing matched.
        process: Result of the coding-agent process, when one ran.
    """

    selected: Task | None
    process: ProcessResult | None = None
