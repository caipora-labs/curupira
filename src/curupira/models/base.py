"""Shared validation primitives for application contracts.

Each validation rule is expressed once as an ``Annotated`` type so that every model
enforcing it shares the same constraints and error messages.
"""

import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

_REPOSITORY_SEGMENT = r"[A-Za-z0-9_.-]+"


def _repository_validator(segments: tuple[str, ...]) -> AfterValidator:
    pattern = re.compile("/".join([_REPOSITORY_SEGMENT] * len(segments)))
    expected = "/".join(segments)

    def validate(value: str) -> str:
        if pattern.fullmatch(value) is None:
            raise ValueError(f"repo must use the {expected} format")
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("repo must not contain traversal segments")
        return value

    return AfterValidator(validate)


def _known_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError(f"unknown timezone: {value}") from error
    return value


def _relative_without_traversal(value: str) -> str:
    if not value.strip():
        raise ValueError("path must not be empty")
    windows_path = PureWindowsPath(value)
    if (
        Path(value).is_absolute()
        or PurePosixPath(value).is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.root)
        or ".." in Path(value).parts
        or ".." in windows_path.parts
    ):
        raise ValueError("path must be relative and must not contain '..'")
    return value


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")]
PositiveSeconds = Annotated[float, Field(gt=0, allow_inf_nan=False)]
BoundedLimit = Annotated[int, Field(strict=True, ge=1, le=1000)]
OutputLimit = Annotated[int, Field(strict=True, ge=1024, le=100_000_000)]
TimezoneName = Annotated[NonEmptyString, AfterValidator(_known_timezone)]
RelativeScriptPath = Annotated[str, AfterValidator(_relative_without_traversal)]
GitHubRepository = Annotated[NonEmptyString, _repository_validator(("owner", "repository"))]
AzureRepository = Annotated[
    NonEmptyString, _repository_validator(("organization", "project", "repository"))
]


class ValidatedModel(BaseModel):
    """Reject unknown fields and validate defaults in immutable model snapshots."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class BoundaryModel(BaseModel):
    """Immutable payload parsed from an external CLI that may add fields at any time."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)
