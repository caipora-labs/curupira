"""Build an interactive assistant launch from settings and the agent registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from curupira.agents import create_cli_adapter
from curupira.agents.assistant import resolve_assistant_model
from curupira.agents.interactive import InteractiveLaunchSpec, default_pty_env, spec_available
from curupira.agents.registry import registered
from curupira.config import ApplicationSettings


@dataclass(frozen=True)
class AssistantLaunchPlan:
    """Resolved plan for mounting the assistant inside a PTY.

    Attributes:
        provider: Registered coding-agent provider name.
        display_name: Human-readable adapter name.
        install_url: Where to install the native CLI when missing.
        spec: Interactive launch recipe, or ``None`` when interactive mode is
            unverified or the executable is missing.
        notice: Optional short note (for example when the model flag is omitted).
        error: User-facing error when the panel cannot start a child process.
    """

    provider: str
    display_name: str
    install_url: str
    spec: InteractiveLaunchSpec | None
    notice: str | None
    error: str | None


def list_assistant_providers() -> list[tuple[str, str]]:
    """Return ``(provider, display_name)`` pairs from the agent registry, sorted."""
    adapters = registered()
    return sorted(
        ((provider, adapter.display_name) for provider, adapter in adapters.items()),
        key=lambda item: item[1].lower(),
    )


def plan_assistant_launch(
    settings: ApplicationSettings,
    *,
    cwd: Path,
) -> AssistantLaunchPlan | None:
    """Resolve the assistant agent into a PTY launch plan.

    Returns ``None`` when ``assistant.agent`` is unset (the panel should ask the user
    which provider to use). Uses :func:`resolve_assistant_model` with the configured
    model (or unset for the adapter's native auto / CLI default), then
    :meth:`~curupira.agents.base.CodingAgentCliAdapter.interactive_launch` with a
    default profile for that provider. Does not invent model flags when the adapter
    has no ``auto_model``.

    Args:
        settings: Loaded application settings.
        cwd: Working directory for the interactive session (project cwd).

    Returns:
        An :class:`AssistantLaunchPlan`, or ``None`` when no agent is chosen yet.
    """
    provider = settings.assistant.agent
    if provider is None:
        return None

    adapter = create_cli_adapter(provider)
    resolved = resolve_assistant_model(adapter, settings.assistant.model)
    # Concrete profile models default ``provider``; validate via the registry class
    # so Pyrefly does not require CliProfileBase's abstract ``provider`` argument.
    profile = adapter.profile_model.model_validate({"provider": adapter.provider})
    spec = adapter.interactive_launch(
        profile,
        model=resolved.model,
        prompt=None,
        cwd=cwd,
    )
    if spec is None:
        return AssistantLaunchPlan(
            provider=provider,
            display_name=adapter.display_name,
            install_url=adapter.install_url,
            spec=None,
            notice=resolved.notice,
            error=(
                f"{adapter.display_name} has no verified interactive launch; "
                "Curupira will not invent CLI flags for an unverified mode."
            ),
        )
    if not spec_available(spec):
        executable = spec.argv[0] if spec.argv else adapter.executable
        return AssistantLaunchPlan(
            provider=provider,
            display_name=adapter.display_name,
            install_url=adapter.install_url,
            spec=None,
            notice=resolved.notice,
            error=(
                f"Executable {executable!r} was not found on PATH. "
                f"Install {adapter.display_name}: {adapter.install_url}"
            ),
        )
    return AssistantLaunchPlan(
        provider=provider,
        display_name=adapter.display_name,
        install_url=adapter.install_url,
        spec=spec,
        notice=resolved.notice,
        error=None,
    )


def pty_environment_for(spec: InteractiveLaunchSpec) -> dict[str, str]:
    """Merge the allowlisted PTY environment with ``spec.env``."""
    return default_pty_env(extra=spec.env)
