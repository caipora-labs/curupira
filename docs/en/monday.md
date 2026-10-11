# monday.com task source

Curupira discovers monday.com board items through the [monday.com GraphQL API](https://developer.monday.com/api-reference/docs)
over `httpx`. Discovery is read-only: Curupira never creates, updates, archives, or
deletes items, and it does not use monday.com CLIs.

## Create an API token

1. In monday.com, open your profile picture → **Developers** (Developer Center).
2. Choose **API token** → **Show**, then copy the personal token.
3. Export it in the environment Curupira runs under, for example:

```sh
export MONDAY_API_TOKEN="your-personal-token"
```

Account admins can also copy a personal token from **Administration** → **Connections** →
**Personal API token**. Curupira reads the token from the environment variable named by
`token_env` (default `MONDAY_API_TOKEN`) and sends it in the `Authorization` header. The
token never appears in logs or error messages.

### Minimum scope

A personal token mirrors your UI permissions. For discovery you need at least
**boards:read** access to the configured board (the ability to open the board in the UI).
Curupira only runs GraphQL queries (`boards` / `items_page` / `next_items_page`); it never
sends mutations.

## Find board and group IDs

Open the board in monday.com. The board ID is the numeric segment in the URL
(`https://<account>.monday.com/boards/<board_id>`). Group IDs appear in the board URL when
you select a group, or in the GraphQL API (`boards { groups { id title } }`). Keep both as
strings in TOML even though they look numeric.

## Configure an automation

Set `trigger_type = "monday-items"`, provide `board_id`, and point `repository` at a
`[repositories.<alias>]` checkout. `group_ids` is optional; when present, only items in
those groups are scheduled. `token_env` defaults to `MONDAY_API_TOKEN`.

```toml
[repositories.product]
remote = "https://github.com/acme/product.git"

[automations.board-items]
trigger_type = "monday-items"
repository = "product"
board_id = "1234567890"
group_ids = ["topics"]
# token_env = "MONDAY_API_TOKEN"
prompt = """
Handle monday.com item ${item_id}: ${item_name}

Group: ${item_group_title} (${item_group_id})
Board: ${board_id}
State: ${item_state}
URL: ${item_url}

${item_columns}
"""
```

`curu validate` checks the automation and prompt placeholders without contacting
monday.com. `curu run` and `curu run --watch` require the token environment variable.

## Prompt placeholders

| Placeholder | Source |
| --- | --- |
| `${item_id}` | Item ID (string) |
| `${item_name}` | Item name |
| `${item_url}` | Item HTML URL |
| `${item_group_id}` | Group ID, or empty |
| `${item_group_title}` | Group title, or empty |
| `${board_id}` | Configured board ID |
| `${item_state}` | Item state (for example `active`) |
| `${item_columns}` | Column values as `column_id: text` lines, or empty |

Common placeholders (`${repository}`, `${automation_id}`, `${task_type}`,
`${task_number}`, `${task_title}`, `${task_url}`, …) still apply. Archived and deleted
items are skipped. Repeated polls are deduplicated by Curupira's normal task feed;
cursor pagination continues across polls when a board has more than one batch.

## Security: item text is untrusted

Item names, column values (`${item_columns}`), and related fields come from anyone who can
edit the board and are placed in the coding agent's prompt, so a hostile editor can try to
steer the agent (prompt injection). Restrict which groups reach the agent with
`group_ids`, and review what your agent profile is allowed to run in the checkout.

## Common errors

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `monday.com API token is missing; set the MONDAY_API_TOKEN…` | Environment variable unset or empty | Export the variable named by `token_env` |
| `authentication failed with status 401` / `403` | Invalid token or no board access | Regenerate the personal token; confirm you can open the board in the UI |
| `monday.com GraphQL error: …` | API `errors[]` (bad board ID, complexity, …) | Read the message; fix `board_id` / `group_ids` or reduce `batch_size` |
| `returned non-JSON` / `missing data` / `unexpected` payload | Corrupt or unexpected response | Retry; if it persists, check monday.com status and API version |
| `temporarily failed with status 429` (or 5xx) | Rate limit or transient outage | Curupira retries a few times; back off or lower poll frequency / `batch_size` |
| No tasks scheduled | Filters match nothing, or all items archived | Widen or drop `group_ids`; confirm the board has active items |

`curu plugins list` shows `monday-items` and its prompt placeholders among built-in
triggers.
