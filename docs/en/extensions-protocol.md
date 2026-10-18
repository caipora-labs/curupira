# Manifest and protocol

The SDKs implement everything on this page for you. Read it when you write an extension
without an SDK, debug one, or want to know exactly what the host does. The normative
specification is
[`PROTOCOL.md`](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-core/PROTOCOL.md).

## Transport { #transport }

Protocol version **2**: JSON-RPC 2.0 over stdin and stdout, in **length-prefixed frames**
(never newline-delimited JSON). Each frame is eight hex digits with the byte length of
the UTF-8 JSON body, followed directly by the body, with no separator and no newline:

```text
0000002c{"jsonrpc":"2.0","id":1,"method":"describe"}
```

- **stdout** carries protocol frames only. **stderr** is for logs.
- The default maximum frame size is 16 MiB.
- The host sends `initialize` with `protocol_version`; the extension answers with the
  same major version. Other versions are rejected with a clear error.

## Methods { #methods }

| Method | When the host calls it |
| --- | --- |
| `initialize` | First, to agree on the protocol version |
| `describe` | To list the triggers |
| `trigger/schema` | To get a trigger's JSON Schema and prompt fields |
| `trigger/validate` | During `curupira validate` and before polling, with the automation's table |
| `trigger/poll` | To get the next item |
| `trigger/onStarted` | Before the coding agent starts, with the item's fields |
| `trigger/onFinished` | After the coding agent finishes, with the item's fields |
| `shutdown` | To let the process exit cleanly |

`trigger/onStarted` and `trigger/onFinished` receive
`{ "trigger_type": "<local>", "values": [ ... ] }`. They do not receive host state such
as the rendered prompt or the worktree path.

## Poll results { #results }

`trigger/poll` always returns an object with a required `values` member:

| `values` | Meaning |
| --- | --- |
| `null` | Nothing was found. The host ends the current round for this automation. |
| `[]` | An item was found, and it has no fields. |
| `[{ "key": "issue_number", "value": "42" }, …]` | The item's fields, as strings. |

Leaving `values` out is a protocol error, distinct from `null`. The protocol does not
require `id`, `title`, `url`, or any other key, and the host does not interpret them.

## What the host does with an item { #polling }

1. It validates the automation with `trigger/validate`, with defaults applied.
2. It calls `trigger/poll` repeatedly, up to `[settings.polling].batch_size` times per
   round. Polling arguments are not passed to the trigger function.
3. It hashes the canonical JSON of the pairs, in the order received, into the task
   identity. A completed identity never runs again; the same pairs in another order are a
   different task.
4. It fills `${key}` in the prompt with each pair's value, in one pass. Inserted text is
   not scanned again, so a value of `${other}` stays literal, and a placeholder with no
   matching key is left unchanged.

The host adds `${repository}` (the forge identity from the Git remote) and
`${automation}` (the automation name). A result key with either name is an error. Keys
that are not identifiers still work: `${issue-number}`, `${foo.bar}`, `${123}`.

## Error codes { #errors }

| Code | Meaning |
| --- | --- |
| `-32700` | Parse error |
| `-32600` | Invalid request |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32000` | Transport failure |
| `-32001` | Protocol or version failure |
| `-32002` | Command execution failure |
| `-32003` | Configuration validation failure |
| `-32004` | Timeout |

## Manifest { #manifest }

`curupira-extension.toml` (manifest format `1`) describes a package so Curupira can list
and install it without running it. An extension must declare `kind = "trigger"` and at
least one entry in `trigger_types`.

```toml
manifest_version = 1
name = "acme-curupira-ext"
version = "1.2.0"
protocol_version = 2
runtime = "node"
kind = "trigger"
trigger_types = ["github-issue"]

[launch]
type = "npx"
package = "@acme/curupira-ext"
version = "1.2.0"
```

The package should print this manifest when started with `--curupira-print-manifest`, so
`curupira plugins list` can describe it without running any trigger code.
