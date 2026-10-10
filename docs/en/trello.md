# Trello task source

Curupira discovers Trello cards through [Scale-Flow/trello-cli](https://github.com/Scale-Flow/trello-cli), a JSON-first CLI. Curupira does not call the Trello HTTP API or change cards.

## Install and authenticate

Install the Scale-Flow CLI:

```sh
brew tap Scale-Flow/tap
brew install trello-cli
```

Or install with Go:

```sh
go install github.com/Scale-Flow/trello-cli/cmd/trello@latest
```

Authenticate once using the device flow:

```sh
trello auth login
```

The CLI prompts you to pair with its Connector Power-Up. For other supported credential flows, see the upstream [getting-started guide](https://github.com/Scale-Flow/trello-cli/blob/main/docs/getting-started.md). Curupira does not store Trello credentials.

## Choose a board and lists

The CLI can list available boards and the lists on one board:

```sh
trello boards list
trello lists list --board <board-id>
trello cards list --board <board-id>
```

Commands return a JSON envelope (`{"ok":true,"data":...}` on success). Curupira reads this structured output directly. Use the board and list IDs in the automation configuration.

## Configure an automation

Set `trigger_type = "trello-cli-cards"`, provide the Trello `board_id`, and keep `repo` pointed at the Git repository that the coding agent should check out. `list_ids` is optional; when present, only cards in those board lists are scheduled.

```toml
[coding_agents.automations.update-board-cards]
trigger_type = "trello-cli-cards"
repo = "acme/product"
board_id = "66f6b55a1a2b3c4d5e6f7788"
list_ids = ["66f6b55a1a2b3c4d5e6f7790"]
prompt = "Handle Trello card ${card_id}: ${card_title}\n\n${card_body}\n\n${card_url}"
```

The `${card_id}`, `${card_title}`, `${card_body}`, `${card_url}`, and `${card_list_id}` prompt fields come from the card. Card IDs remain strings. Repeated polls are deduplicated by Curupira's normal task feed. `curu validate` validates the automation without contacting Trello; `curu run` and
`curu run --watch` require the CLI to be installed and authenticated.

If the executable is missing, install Scale-Flow's `trello-cli`. For authentication failures, run `trello auth login`. Invalid JSON and CLI failures are reported as discovery errors.
