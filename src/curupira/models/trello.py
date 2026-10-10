"""Validated payloads returned by Scale-Flow's Trello CLI."""

from pydantic import BaseModel, ConfigDict, Field

from curupira.models.base import NonEmptyString, ValidatedModel


class TrelloBoard(BaseModel):
    """A Trello board returned by ``trello boards list``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: NonEmptyString
    name: str


class TrelloList(BaseModel):
    """A Trello list returned by ``trello lists list``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: NonEmptyString
    name: str


class TrelloCard(BaseModel):
    """A Trello card returned by ``trello cards list``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: NonEmptyString
    name: str
    desc: str = ""
    url: NonEmptyString
    id_list: NonEmptyString = Field(validation_alias="idList")
    closed: bool = False


class TrelloListRequest(ValidatedModel):
    """A board/list scope accepted by Trello card discovery."""

    board_id: NonEmptyString
    list_ids: tuple[NonEmptyString, ...] | None = None
