"""Validated requests and results for subprocess execution."""

from pathlib import Path

from pydantic import Field

from opscli.models.base import NonEmptyString, PositiveSeconds, ValidatedModel
from opscli.models.profiles import CliProfile, OpenCodeCliProfile
from opscli.models.tasks import Task


class CodingTaskRequest(ValidatedModel):
    """A native CLI invocation with validated provider options."""

    cwd: Path
    message: NonEmptyString
    profile: CliProfile = Field(default_factory=OpenCodeCliProfile)
    session_id: NonEmptyString | None = None
    timeout: PositiveSeconds | None = None
    max_output_bytes: int = Field(default=1_000_000, ge=1024, le=100_000_000)


class CommandRequest(ValidatedModel):
    """An argument vector executed directly, never through a shell."""

    executable: NonEmptyString
    arguments: tuple[str, ...] = ()
    cwd: Path | None = None
    timeout: PositiveSeconds | None = 30.0
    capture_output: bool = True
    max_output_bytes: int = Field(default=1_000_000, ge=1024, le=100_000_000)


class ProcessResult(ValidatedModel):
    """A process exit status and bounded text output."""

    returncode: int
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False


class DispatchOutcome(ValidatedModel):
    """The selected task and optional process result from one-shot dispatch."""

    selected: Task | None
    process: ProcessResult | None = None
