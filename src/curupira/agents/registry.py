"""Registry for built-in and plugin coding-agent adapters."""

from curupira.agents.base import CodingAgentCliAdapter

_ADAPTERS: dict[str, type[CodingAgentCliAdapter]] = {}


def register(adapter_cls: type[CodingAgentCliAdapter]) -> None:
    """Register one coding-agent adapter class for its declared provider."""
    provider = adapter_cls.provider
    if provider in _ADAPTERS:
        raise ValueError(f"coding agent provider already registered: {provider}")
    _validate_profile_model(adapter_cls)
    _ADAPTERS[provider] = adapter_cls


def get(provider: str) -> type[CodingAgentCliAdapter]:
    """Return the adapter class for a provider, or raise an actionable error."""
    _ensure_loaded()
    try:
        return _ADAPTERS[provider]
    except KeyError as error:
        raise ValueError(f"unknown coding agent provider: {provider}") from error


def registered() -> dict[str, type[CodingAgentCliAdapter]]:
    """Return every registered provider, built-in adapters first."""
    _ensure_loaded()
    return dict(_ADAPTERS)


def _ensure_loaded() -> None:
    # Built-ins register through Pluggy and must precede plugins so collisions are rejected.
    from curupira.manager import load_built_in_providers
    from curupira.plugins import load_agent_plugins

    load_built_in_providers()
    load_agent_plugins()


def _validate_profile_model(adapter_cls: type[CodingAgentCliAdapter]) -> None:
    from curupira.models.profiles import CliProfileBase

    provider = adapter_cls.provider
    model = getattr(adapter_cls, "profile_model", None)
    if not isinstance(model, type) or not issubclass(model, CliProfileBase):
        raise ValueError(
            f"coding agent {provider!r} must declare a profile_model that extends CliProfileBase"
        )
    default = model.model_fields["provider"].default
    if default != provider:
        raise ValueError(
            f"profile_model for {provider!r} must default provider to {provider!r}, not {default!r}"
        )
