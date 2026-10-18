# Curupira extension protocol

Version **2**. Transport: **JSON-RPC 2.0** over **stdin/stdout** with
**length-prefixed frames** (never newline-delimited JSON).

Extensions contribute **task sources** (triggers) only. Coding-agent adapters are
built into the Rust CLI and are not launched through this protocol.

## Framing

Each message is:

```
XXXXXXXX<utf-8 JSON body>
```

where `XXXXXXXX` is eight lowercase or uppercase ASCII hex digits giving the
byte length of the JSON body (big-endian interpretation of the hex integer). The
body follows the header directly, with no separator and no trailing newline.

- **stdout** is reserved for protocol frames only.
- **stderr** is for logs and diagnostics.
- Default maximum frame size: **16 MiB** (host-configurable).

## Version negotiation

The host sends `initialize` with `protocol_version`. The extension must reply
with the same major protocol version it implements. The host rejects incompatible
versions with a clear error (never silently).

Current version: `2`. Compatible range for this host: `2..=2`.
Version 1 extensions are rejected at `initialize`.

## Methods

| Method | Direction | Purpose |
| --- | --- | --- |
| `initialize` | host → ext | Negotiate version; identify peers |
| `describe` | host → ext | List triggers (and an empty `agents` array for wire compatibility) |
| `trigger/schema` | host → ext | JSON Schema + prompt fields |
| `trigger/validate` | host → ext | Validate an automation table |
| `trigger/poll` | host → ext | Discover the next result (`values`: JSON `null` or a list of string pairs) |
| `trigger/onStarted` | host → ext | Lifecycle before coding agent; receives the result pairs |
| `trigger/onFinished` | host → ext | Lifecycle after coding agent; receives the result pairs |
| `shutdown` | host → ext | Graceful exit |

### Error codes

| Code | Meaning |
| --- | --- |
| `-32700` | Parse error |
| `-32600` | Invalid request |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32000` | Transport failure |
| `-32001` | Protocol / version failure |
| `-32002` | Command execution failure |
| `-32003` | Configuration validation failure |
| `-32004` | Timeout |

## Trigger result

`trigger/poll` returns one logical result. The method result is always a JSON
object so a JSON-RPC `result` of `null` is not used:

```json
{ "values": null }
```

```json
{ "values": [] }
```

```json
{ "values": [{ "key": "issue-number", "value": "42" }] }
```

| `values` | Meaning |
| --- | --- |
| `null` | No item was found. The host stops the current poll round. |
| `[]` | An item was found and it has no pairs. |
| a list | The pairs that represent the item. |

`values` is required. Omitting it is a protocol error, distinct from `null`.
Each element is an object with string fields `key` and `value` only. The
protocol does not require `id`, `number`, `title`, `url`, `item`, or any other
name, and it does not interpret the pairs.

`trigger/onStarted` and `trigger/onFinished` receive
`{ "trigger_type": "<local>", "values": [ ... ] }` for the result that is
running. They do not receive host state such as the rendered prompt, repository
checkout, or worktree path.

Configuration (`trigger/validate`, `trigger/schema`) is a separate contract.
Generalizing the result does not remove typed validation of automation
parameters.

The host turns the list into a task identity by hashing the canonical JSON of
the pairs in the order received. The same list is not executed again after it
completes. A different list, including the same pairs in another order, is a
different task. That identity is not a field the extension sends.

Prompt placeholders are `${key}` for each pair, plus the host variables
`${repository}` and `${automation}`. See the extension guide for conversion
and interpolation rules.

## Manifest

File name: `curupira-extension.toml` (manifest format version `1`).

Manifests must declare at least one `trigger_types` entry and `kind = "trigger"`.
Coding-agent-only manifests (`kind = "agent"` or non-empty `agent_providers`) are
rejected; agents are built into the core.

Discovery reads manifests from:

1. `~/.curupira/extensions/<name>/`
2. `CURUPIRA_EXTENSIONS_PATH` (colon/semicolon-separated directories)
3. Bundled `packages/curupira-python-plugins/` when running from a checkout

Listing installed extensions **never** executes extension code.

## Security

Installing or running a third-party extension executes that code. Subprocesses
are **not** a sandbox. The host does not install packages during discovery.
Install commands require explicit confirmation unless `--yes` is passed.
Argv are passed as separate process arguments (never a shell string).
