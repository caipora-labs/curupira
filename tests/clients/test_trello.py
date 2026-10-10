"""Scale-Flow Trello CLI client contracts."""

import json
from collections.abc import Awaitable, Callable

import pytest
from typing_extensions import override

from curupira.clients.process import AsyncProcessRunner
from curupira.clients.trello import TrelloClient
from curupira.errors import CliExecutionError, CliNotFoundError, CliOutputError
from curupira.models import CommandRequest, ProcessResult, TrelloListRequest


class FakeRunner(AsyncProcessRunner):
    """Return queued CLI outputs while recording exact argument vectors."""

    def __init__(self, results: list[ProcessResult | Exception]) -> None:
        super().__init__()
        self.results = results
        self.requests: list[CommandRequest] = []

    @override
    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        del on_stdout_line
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def success(data: object) -> ProcessResult:
    """Wrap fixture data in the CLI's documented success envelope."""
    return ProcessResult(returncode=0, stdout=json.dumps({"ok": True, "data": data}))


@pytest.mark.asyncio
async def test_lists_boards_lists_and_board_cards_with_documented_commands() -> None:
    runner = FakeRunner(
        [
            success([{"id": "b-1", "name": "Roadmap"}]),
            success([{"id": "l-1", "name": "Ready"}]),
            success(
                [
                    {
                        "id": "66f6b55a1a2b3c4d5e6f7788",
                        "name": "Ship feature",
                        "desc": "Details",
                        "url": "https://trello.com/c/abc123",
                        "idList": "l-1",
                        "closed": False,
                    }
                ]
            ),
        ]
    )
    client = TrelloClient(runner)

    boards = await client.list_boards()
    lists = await client.list_lists("b-1")
    cards = await client.list_cards(TrelloListRequest(board_id="b-1"))

    assert boards[0].id == "b-1"
    assert lists[0].name == "Ready"
    assert cards[0].id == "66f6b55a1a2b3c4d5e6f7788"
    assert runner.requests == [
        CommandRequest(executable="trello", arguments=("boards", "list")),
        CommandRequest(executable="trello", arguments=("lists", "list", "--board", "b-1")),
        CommandRequest(executable="trello", arguments=("cards", "list", "--board", "b-1")),
    ]


@pytest.mark.asyncio
async def test_empty_envelope_and_list_filter_are_supported() -> None:
    runner = FakeRunner(
        [
            success([]),
            success(
                [
                    {
                        "id": "card-1",
                        "name": "Keep",
                        "url": "https://trello.com/c/1",
                        "idList": "chosen",
                    },
                    {
                        "id": "card-2",
                        "name": "Skip",
                        "url": "https://trello.com/c/2",
                        "idList": "other",
                    },
                ]
            ),
        ]
    )
    client = TrelloClient(runner)

    assert await client.list_boards() == []
    cards = await client.list_cards(TrelloListRequest(board_id="board", list_ids=("chosen",)))

    assert [card.id for card in cards] == ["card-1"]


@pytest.mark.asyncio
async def test_cli_authentication_error_has_login_guidance() -> None:
    client = TrelloClient(
        FakeRunner(
            [
                ProcessResult(
                    returncode=1,
                    stdout=(
                        '{"ok":false,"error":{"code":"AUTH_REQUIRED",'
                        '"message":"not authenticated"}}'
                    ),
                )
            ]
        )
    )

    with pytest.raises(CliExecutionError, match="trello auth login"):
        await client.list_boards()


@pytest.mark.asyncio
async def test_invalid_json_and_envelope_raise_output_errors() -> None:
    runner = FakeRunner(
        [
            ProcessResult(returncode=0, stdout="not json"),
            ProcessResult(returncode=0, stdout='{"ok":false,"error":{}}'),
        ]
    )
    client = TrelloClient(runner)

    with pytest.raises(CliOutputError, match="invalid boards JSON"):
        await client.list_boards()
    with pytest.raises(CliOutputError, match="trello command failed"):
        await client.list_boards()


@pytest.mark.asyncio
async def test_missing_cli_has_scale_flow_install_guidance() -> None:
    client = TrelloClient(FakeRunner([CliNotFoundError("trello")]))

    with pytest.raises(CliNotFoundError, match="Scale-Flow/trello-cli"):
        await client.list_boards()
