"""Validated payloads returned by the monday.com GraphQL API."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from curupira.models.base import NonEmptyString, ValidatedModel


def _coerce_identifier(value: object) -> object:
    """Accept numeric JSON IDs while normalizing them to stable strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    return value


class MondayGroup(BaseModel):
    """A monday.com group nested under a board item."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: NonEmptyString
    title: str = ""

    @field_validator("id", mode="before")
    @classmethod
    def preserve_identifier(cls, value: object) -> object:
        """Keep group IDs as strings even when JSON encodes them as numbers."""
        return _coerce_identifier(value)


class MondayColumnValue(BaseModel):
    """One column value on a monday.com item."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: NonEmptyString
    text: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def preserve_identifier(cls, value: object) -> object:
        """Keep column IDs as strings even when JSON encodes them as numbers."""
        return _coerce_identifier(value)


class MondayBoardItem(BaseModel):
    """A monday.com board item returned by ``items_page`` / ``next_items_page``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: NonEmptyString
    name: str
    url: NonEmptyString
    state: str = "active"
    group: MondayGroup | None = None
    column_values: tuple[MondayColumnValue, ...] = ()

    @field_validator("id", mode="before")
    @classmethod
    def preserve_identifier(cls, value: object) -> object:
        """Keep item IDs as strings even when JSON encodes them as numbers."""
        return _coerce_identifier(value)


class MondayItemsPage(ValidatedModel):
    """One cursor page of monday.com board items."""

    items: tuple[MondayBoardItem, ...]
    cursor: str | None = None


class MondayListRequest(ValidatedModel):
    """A board/group scope and page position for monday.com item discovery."""

    board_id: NonEmptyString
    group_ids: tuple[NonEmptyString, ...] | None = None
    cursor: str | None = None
    limit: int = Field(ge=1, le=500)
