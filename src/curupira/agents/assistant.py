"""Resolve the configuration assistant's model against adapter capabilities."""

from dataclasses import dataclass

from curupira.agents.base import CodingAgentCliAdapter


@dataclass(frozen=True)
class ResolvedModel:
    """Outcome of mapping a requested assistant model to a CLI model flag.

    Attributes:
        model: Value to pass as the CLI model, or ``None`` to omit the flag.
        notice: Optional user-facing explanation when the model flag is omitted.
    """

    model: str | None
    notice: str | None


def resolve_assistant_model(
    adapter: CodingAgentCliAdapter | type[CodingAgentCliAdapter],
    requested: str | None,
) -> ResolvedModel:
    """Map an optional requested model to the value the assistant CLI should receive.

    When ``requested`` is unset, providers that declare ``auto_model`` use that value;
    otherwise the model flag is omitted and a notice explains that the CLI's own default
    applies. The literal ``auto`` is rejected when the adapter has no native auto.
    Any other requested value is passed through unchanged.
    """
    auto_model = adapter.auto_model
    provider = adapter.provider
    if requested is None:
        if auto_model is not None:
            return ResolvedModel(model=auto_model, notice=None)
        return ResolvedModel(
            model=None,
            notice=(
                f"coding agent provider {provider!r} has no native automatic model "
                "selection; the CLI's own default model will be used"
            ),
        )
    if requested == "auto" and auto_model is None:
        raise ValueError(
            f"coding agent provider {provider!r} has no native automatic model "
            "selection; set assistant.model to a concrete model name or leave it unset"
        )
    return ResolvedModel(model=requested, notice=None)
