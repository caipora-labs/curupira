"""Typed asynchronous client for Scale-Flow's Trello CLI."""

import json
from typing import TypeVar

from pydantic import TypeAdapter, ValidationError

from curupira.clients.process import AsyncProcessRunner
from curupira.errors import CliExecutionError, CliNotFoundError, CliOutputError
from curupira.models import CommandRequest, TrelloBoard, TrelloCard, TrelloList
from curupira.models.trello import TrelloListRequest

TModel = TypeVar("TModel", TrelloBoard, TrelloList, TrelloCard)


class TrelloClient:
    """List boards, lists, and cards through the JSON-first ``trello`` executable."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()

    async def list_boards(self) -> list[TrelloBoard]:
        """Return boards visible to the authenticated Trello CLI user."""
        return await self._list(("boards", "list"), TrelloBoard)

    async def list_lists(self, board_id: str) -> list[TrelloList]:
        """Return lists on a Trello board."""
        return await self._list(("lists", "list", "--board", board_id), TrelloList)

    async def list_cards(self, request: TrelloListRequest) -> list[TrelloCard]:
        """Return cards from a board, optionally restricted to selected list IDs."""
        cards = await self._list(("cards", "list", "--board", request.board_id), TrelloCard)
        if request.list_ids is None:
            return cards
        allowed_lists = set(request.list_ids)
        return [card for card in cards if card.id_list in allowed_lists]

    async def _list(
        self,
        arguments: tuple[str, ...],
        model: type[TModel],
    ) -> list[TModel]:
        request = CommandRequest(executable="trello", arguments=arguments)
        try:
            result = await self._runner.run(request)
        except CliNotFoundError as error:
            raise CliNotFoundError(
                "trello (install Scale-Flow/trello-cli: brew tap Scale-Flow/tap && "
                "brew install trello-cli)"
            ) from error
        if result.returncode != 0:
            message = _error_message(result.stdout, result.stderr)
            if _is_authentication_error(message):
                message = f"{message}. Authenticate with `trello auth login`."
            raise CliExecutionError("trello", result.returncode, message)
        try:
            envelope = json.loads(result.stdout)
            if not isinstance(envelope, dict):
                raise TypeError("expected a JSON object envelope")
            if envelope.get("ok") is False:
                message = _envelope_error_message(envelope)
                if _is_authentication_error(message):
                    message = f"{message}. Authenticate with `trello auth login`."
                raise CliOutputError(f"trello command failed: {message}")
            if envelope.get("ok") is not True:
                raise TypeError('expected a successful {"ok":true,"data":...} envelope')
            if "data" not in envelope:
                raise TypeError("successful envelope is missing data")
            return TypeAdapter(list[model]).validate_python(envelope["data"])
        except (json.JSONDecodeError, TypeError, ValidationError) as error:
            raise CliOutputError(f"trello returned invalid {arguments[0]} JSON: {error}") from error


def _error_message(stdout: str, stderr: str) -> str:
    """Extract the CLI error message from its JSON envelope or stderr."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        message = _envelope_error_message(payload)
        if message:
            return message
    return stderr.strip() or stdout.strip() or "no error details were provided"


def _envelope_error_message(envelope: dict[str, object]) -> str:
    """Extract a documented CLI error message, if present."""
    error = envelope.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    return "trello-cli returned an error envelope without a message"


def _is_authentication_error(message: str) -> bool:
    """Recognize common Trello CLI authentication failures."""
    normalized = message.lower()
    return any(
        marker in normalized
        for marker in (
            "unauthorized",
            "not authenticated",
            "auth required",
            "authentication required",
            "missing credentials",
            "invalid credentials",
        )
    )
