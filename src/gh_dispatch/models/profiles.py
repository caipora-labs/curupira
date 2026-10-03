"""Provider-native CLI profiles; these reference agents, not define them."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from gh_dispatch.models.base import NonEmptyString, ValidatedModel


class CliProfileBase(ValidatedModel):
    """Options common to every supported CLI."""

    model: NonEmptyString | None = None


class OpenCodeCliProfile(CliProfileBase):
    """OpenCode options, including native custom-agent selection."""

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
    """Codex options; a configuration profile is not a custom agent."""

    provider: Literal["codex"] = "codex"
    effort: Literal["minimal", "low", "medium", "high", "xhigh", "max", "ultra"] | None = None
    sandbox: Literal["read-only", "workspace-write", "danger-full-access"] | None = None
    auto_review: bool = False

    @model_validator(mode="after")
    def validate_approval_options(self) -> "CodexCliProfile":
        """Require compatible Codex approval options."""
        if self.auto_review and self.sandbox not in {None, "workspace-write"}:
            raise ValueError("Codex auto_review requires the workspace-write sandbox")
        return self


class ClaudeCodeCliProfile(CliProfileBase):
    """Claude Code options, including native custom-agent selection."""

    provider: Literal["claude"] = "claude"
    agent: NonEmptyString | None = None
    effort: Literal["low", "medium", "high", "xhigh", "max", "ultracode"] | None = None
    permission_mode: (
        Literal["default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions"] | None
    ) = None
    permission_prompts: Literal["host", "none"] | None = None


class CursorCliProfile(CliProfileBase):
    """Cursor options; modes and custom agents are distinct concepts."""

    provider: Literal["cursor"] = "cursor"
    force: bool = False
    trust: bool = False


CliProfile = Annotated[
    OpenCodeCliProfile | CodexCliProfile | ClaudeCodeCliProfile | CursorCliProfile,
    Field(discriminator="provider"),
]
