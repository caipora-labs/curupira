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

### Access required

A personal API token has every GraphQL scope and mirrors the owner's UI permissions (app
tokens are the ones that declare scopes). For discovery, the token owner must be able to
**open the configured board in the monday.com UI**. Curupira only runs GraphQL queries
(`boards` / `items_page` / `next_items_page`); it never sends mutations.

## Find board and group IDs

Open the board in monday.com. The board ID is the numeric segment in the URL
(`https://<account>.monday.com/boards/<board_id>`). List groups with GraphQL; IDs are
strings such as `topics` or `new_group12345`:

```sh
curl -s -X POST https://api.monday.com/v2 \
  -H "Authorization: $MONDAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "API-Version: 2026-07" \
  -d '{"query":"query { boards(ids: [1234567890]) { groups { id title } } }"}'
```

Keep board and group IDs as strings in TOML.

## Configure an automation

The following snippet is a complete settings file that passes `curupira validate` (no
network). Set `trigger_type = "monday-items"`, provide `board_id`, and point `repository`
at a `[repositories.<alias>]` checkout. `group_ids` is optional; when present, only items
in those groups are scheduled. `token_env` defaults to `MONDAY_API_TOKEN`.

```toml
[repositories.product]
remote = "https://github.com/acme/product.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

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

## Pagination, deduplication, and rate limits

Cursor pagination continues across polls while Curupira is running: when a poll fills
`settings.polling.batch_size`, the next poll resumes from the opaque monday.com cursor
instead of re-reading the first page. Both the cursor and `PollingTaskFeed` deduplication
are **in-memory only**. After a process restart, discovery starts again from the first
page and previously handled item IDs may be re-emitted until the feed rebuilds its seen
set.

When the board is fully scanned, the cursor resets and the next cycle starts from the
beginning. Items created at the top of a group after a cycle has already moved past that
position appear only on a later cycle.

monday.com free/standard/basic plans allow **1,000 API calls per day** (resets at midnight
UTC). Prefer a larger `settings.polling.poll_interval_seconds` (and a modest `batch_size`)
so idle watching does not burn the daily quota; each page fetch is one GraphQL call.

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
items are skipped when present in a response.

## Security: item text is untrusted

Item names, column values (`${item_columns}`), and related fields come from anyone who can
edit the board and are placed in the coding agent's prompt, so a hostile editor can try to
steer the agent (prompt injection). Restrict which groups reach the agent with
`group_ids`, and review what your agent profile is allowed to run in the checkout.

## Common errors

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `monday.com API token is missing; set the MONDAY_API_TOKEN…` | Environment variable unset or empty | Export the variable named by `token_env` |
| `authentication failed with status 401` / `403` | Invalid token or owner cannot open the board | Regenerate the personal token; confirm the token owner can open the board in the UI |
| `board … not found or not accessible` | Wrong `board_id` or no UI access | Fix `board_id`; open the board while logged in as the token owner |
| `query complexity exceeds` / reduce `batch_size` | Single query over the 5M complexity limit | Lower `settings.polling.batch_size` |
| `monday.com GraphQL error: …` | Other API `errors[]` | Read the message; fix `board_id` / `group_ids` |
| `returned non-JSON` / `missing data` / `unexpected` payload | Corrupt or unexpected response | Retry; if it persists, check monday.com status and API version |
| `temporarily failed with status 429` (or 5xx) | Rate limit or transient outage | Curupira honors `Retry-After` / `retry_in_seconds` and retries a few times; raise `poll_interval_seconds` or lower `batch_size` |
| No tasks scheduled | Filters match nothing | Widen or drop `group_ids`; confirm the board has active items |

`curu plugins list` shows `monday-items` and its prompt placeholders among built-in
triggers.
