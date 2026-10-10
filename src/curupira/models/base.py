"""Shared validation primitives for application contracts."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")]
PositiveSeconds = Annotated[float, Field(gt=0, allow_inf_nan=False)]
PositiveMinutes = Annotated[int, Field(strict=True, gt=0)]


class ValidatedModel(BaseModel):
    """Reject unknown fields and validate defaults in immutable model snapshots."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
