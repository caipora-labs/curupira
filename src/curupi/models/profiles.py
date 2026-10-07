"""Provider-native CLI profiles; these reference agents, not define them."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from curupi.models.base import NonEmptyString, ValidatedModel


class CliProfileBase(ValidatedModel):
    """Options common to every supported CLI.

    Attributes:
        model: Optional provider-specific model identifier.
    """

    model: NonEmptyString | None = None


class OpenCodeCliProfile(CliProfileBase):
    """OpenCode options, including native custom-agent selection.

    Attributes:
        provider: Discriminator identifying the OpenCode CLI.
        agent: Optional configured OpenCode agent name.
        effort: Optional provider-specific effort level.
        auto_approve: Whether OpenCode runs with approval prompts disabled.
    """

    provider: Literal["opencode"] = "opencode"
    agent: NonEmptyString | None = None
    effort: NonEmptyString | None = None
    auto_approve: bool = False

    @model_validator(mode="after")
    def validate_model_format(self) -> "OpenCodeCliProfile":
        """Require the provider/model format."""
        if self.model is not None and "/" not in self.model:
            raise ValueError("OpenCode model must use the provider/model format")
        return self


class CodexCliProfile(CliProfileBase):
    """Codex options, including selection of an existing CLI configuration profile.

    Attributes:
        provider: Discriminator identifying the Codex CLI.
        agent: Optional configured Codex agent name.
        effort: Optional Codex reasoning effort.
        sandbox: Optional Codex sandbox permission level.
        auto_review: Whether Codex should review changes automatically.
    """

    provider: Literal["codex"] = "codex"
    agent: NonEmptyString | None = None
    effort: Literal["low", "medium", "high", "xhigh", "max", "ultra"] | None = None
    sandbox: Literal["read-only", "workspace-write", "danger-full-access"] | None = None
    auto_review: bool = False

    @model_validator(mode="after")
    def validate_approval_options(self) -> "CodexCliProfile":
        """Require compatible Codex approval options."""
        if self.auto_review and self.sandbox not in {None, "workspace-write"}:
            raise ValueError("Codex auto_review requires the workspace-write sandbox")
        return self


class ClaudeCodeCliProfile(CliProfileBase):
    """Claude Code options, including native custom-agent selection.

    Attributes:
        provider: Discriminator identifying the Claude Code CLI.
        agent: Optional configured Claude Code agent name.
        effort: Optional Claude model effort level.
        permission_mode: Optional Claude Code permission mode.
        permission_prompts: Whether permission prompts are handled by the host or disabled.
    """

    provider: Literal["claude"] = "claude"
    agent: NonEmptyString | None = None
    effort: Literal["low", "medium", "high", "xhigh", "max", "ultracode"] | None = None
    permission_mode: (
        Literal["default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions"] | None
    ) = None
    permission_prompts: Literal["host", "none"] | None = None


class CursorCliProfile(CliProfileBase):
    """Cursor options, including native agent/ask/plan mode selection.

    Attributes:
        provider: Discriminator identifying the Cursor CLI.
        agent: Optional Cursor execution mode.
        force: Whether to force execution in a non-interactive environment.
        trust: Whether to trust the current workspace.
    """

    provider: Literal["cursor"] = "cursor"
    agent: Literal["agent", "ask", "plan"] | None = None
    force: bool = False
    trust: bool = False


CliProfile = Annotated[
    OpenCodeCliProfile | CodexCliProfile | ClaudeCodeCliProfile | CursorCliProfile,
    Field(discriminator="provider"),
]
