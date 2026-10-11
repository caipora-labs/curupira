"""Provider-native CLI profiles; these reference agents, not define them."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, SerializeAsAny, model_validator

from curupira.models.base import NonEmptyString, ValidatedModel


class CliProfileBase(ValidatedModel):
    """Options common to every supported coding-agent CLI profile.

    Agent plugins extend this model and give ``provider`` a default equal to their
    registered provider name.
    """

    provider: NonEmptyString = Field(
        description=(
            "Registered coding-agent provider name that selects which profile model "
            "and adapter Curupira uses for this profile table."
        ),
    )
    model: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional provider-specific model identifier. When set, built-in adapters "
            "pass it as ``--model``; when unset, that flag is omitted."
        ),
    )


class OpenCodeCliProfile(CliProfileBase):
    """OpenCode CLI profile. Set ``provider`` to ``\"opencode\"`` in TOML.

    When ``model`` is set it must use the ``provider/model`` format.
    """

    provider: Literal["opencode"] = Field(
        default="opencode",
        description='Discriminator identifying the OpenCode CLI. Must be "opencode".',
    )
    agent: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional configured OpenCode agent name. When set, the adapter passes "
            "``--agent``; when unset, that flag is omitted."
        ),
    )
    effort: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional OpenCode reasoning variant. When set, the adapter passes "
            "``--variant``; when unset, that flag is omitted."
        ),
    )
    auto_approve: bool = Field(
        default=False,
        description=(
            "When true, the adapter adds ``--auto`` so OpenCode runs with approval "
            "prompts disabled. When false (the default), that flag is omitted."
        ),
    )

    @model_validator(mode="after")
    def validate_model_format(self) -> "OpenCodeCliProfile":
        """Require the provider/model format."""
        if self.model is not None and "/" not in self.model:
            raise ValueError("OpenCode model must use the provider/model format")
        return self


class CodexCliProfile(CliProfileBase):
    """Codex CLI profile. Set ``provider`` to ``\"codex\"`` in TOML."""

    provider: Literal["codex"] = Field(
        default="codex",
        description='Discriminator identifying the Codex CLI. Must be "codex".',
    )
    agent: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional configured Codex CLI configuration profile name. When set, the "
            "adapter passes ``--profile``; when unset, that flag is omitted."
        ),
    )
    effort: Literal["low", "medium", "high", "xhigh", "max", "ultra"] | None = Field(
        default=None,
        description=(
            "Optional Codex reasoning effort. Allowed values: low, medium, high, "
            "xhigh, max, ultra. When set, the adapter passes "
            "``--config model_reasoning_effort=<json>``; when unset, that flag is omitted."
        ),
    )
    sandbox: Literal["read-only", "workspace-write", "danger-full-access"] | None = Field(
        default=None,
        description=(
            "Optional Codex sandbox permission level. Allowed values: read-only, "
            "workspace-write, danger-full-access. When set, the adapter passes "
            "``--sandbox``; when unset, that flag is omitted."
        ),
    )
    auto_review: bool = Field(
        default=False,
        description=(
            "When true, the adapter adds ``--config approval_policy=\"on-request\"`` and "
            "``--config approvals_reviewer=\"auto_review\"``. Requires ``sandbox`` to be "
            "unset or ``workspace-write``. When false (the default), those flags are omitted."
        ),
    )

    @model_validator(mode="after")
    def validate_approval_options(self) -> "CodexCliProfile":
        """Require compatible Codex approval options."""
        if self.auto_review and self.sandbox not in {None, "workspace-write"}:
            raise ValueError("Codex auto_review requires the workspace-write sandbox")
        return self


class ClaudeCodeCliProfile(CliProfileBase):
    """Claude Code CLI profile. Set ``provider`` to ``\"claude\"`` in TOML."""

    provider: Literal["claude"] = Field(
        default="claude",
        description='Discriminator identifying the Claude Code CLI. Must be "claude".',
    )
    agent: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional configured Claude Code agent name. When set, the adapter passes "
            "``--agent``; when unset, that flag is omitted."
        ),
    )
    effort: Literal["low", "medium", "high", "xhigh", "max", "ultracode"] | None = Field(
        default=None,
        description=(
            "Optional Claude model effort level. Allowed values: low, medium, high, "
            "xhigh, max, ultracode. When set, the adapter passes ``--effort``; when "
            "unset, that flag is omitted."
        ),
    )
    permission_mode: (
        Literal["default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions"] | None
    ) = Field(
        default=None,
        description=(
            "Optional Claude Code permission mode. Allowed values: default, acceptEdits, "
            "plan, auto, dontAsk, bypassPermissions. When set, the adapter passes "
            "``--permission-mode``; when unset, that flag is omitted."
        ),
    )
    permission_prompts: Literal["host", "none"] | None = Field(
        default=None,
        description=(
            "Optional Claude Code permission-prompt handling. Allowed values: host, none. "
            "When set, the adapter passes ``--permission-prompts``; when unset, that flag "
            "is omitted."
        ),
    )


class CursorCliProfile(CliProfileBase):
    """Cursor CLI profile. Set ``provider`` to ``\"cursor\"`` in TOML."""

    provider: Literal["cursor"] = Field(
        default="cursor",
        description='Discriminator identifying the Cursor CLI. Must be "cursor".',
    )
    agent: Literal["agent", "ask", "plan"] | None = Field(
        default=None,
        description=(
            "Optional Cursor execution mode. Allowed values: agent, ask, plan. When set, "
            "the adapter passes ``--mode``; when unset, that flag is omitted."
        ),
    )
    force: bool = Field(
        default=False,
        description=(
            "When true, the adapter adds ``--force``. When false (the default), that flag "
            "is omitted."
        ),
    )
    trust: bool = Field(
        default=False,
        description=(
            "When true, the adapter adds ``--trust``. When false (the default), that flag "
            "is omitted."
        ),
    )


def parse_cli_profile(value: object) -> object:
    """Validate a profile table with the model of its registered coding agent."""
    if not isinstance(value, dict):
        return value
    from curupira.agents.registry import get

    provider = value.get("provider")
    if provider is None:
        raise ValueError("provider is required")
    if not isinstance(provider, str):
        raise ValueError("provider must be a string")
    return get(provider).profile_model.model_validate(value)


# SerializeAsAny keeps plugin-specific fields when snapshots are dumped and revalidated.
CliProfile = Annotated[SerializeAsAny[CliProfileBase], BeforeValidator(parse_cli_profile)]
