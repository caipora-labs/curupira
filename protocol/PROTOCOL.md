# Curupira extension protocol

Version **1**. Transport: **JSON-RPC 2.0** over **stdin/stdout** with
**length-prefixed frames** (never newline-delimited JSON).

## Framing

Each message is:

```
XXXXXXXX <utf-8 JSON body>
```

where `XXXXXXXX` is eight lowercase or uppercase ASCII hex digits giving the
byte length of the JSON body (big-endian interpretation of the hex integer).

- **stdout** is reserved for protocol frames only.
- **stderr** is for logs and diagnostics.
- Default maximum frame size: **16 MiB** (host-configurable).

## Version negotiation

The host sends `initialize` with `protocol_version`. The extension must reply
with the same major protocol version it implements. The host rejects incompatible
versions with a clear error (never silently).

Current version: `1`. Compatible range for this host: `1..=1`.

## Methods

| Method | Direction | Purpose |
| --- | --- | --- |
| `initialize` | host → ext | Negotiate version; identify peers |
| `describe` | host → ext | List triggers and agents |
| `trigger/schema` | host → ext | JSON Schema + prompt fields |
| `trigger/validate` | host → ext | Validate an automation table |
| `trigger/poll` | host → ext | Discover the next available task (`task` object or JSON `null`). `null` ends the round; never return a task array. |
| `trigger/onStarted` | host → ext | Lifecycle before coding agent |
| `trigger/onFinished` | host → ext | Lifecycle after coding agent |
| `agent/buildArguments` | host → ext | Build argv for a coding-agent CLI |
| `agent/interactiveLaunch` | host → ext | Optional TUI assistant launch |
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

## Manifest

File name: `curupira-extension.toml` (manifest format version `1`).

Discovery reads manifests from:

1. `~/.curupira/extensions/<name>/`
2. `CURUPIRA_EXTENSIONS_PATH` (colon/semicolon-separated directories)
3. Bundled `plugins/` next to the checkout or install share

Listing installed extensions **never** executes extension code.

## Security

Installing or running a third-party extension executes that code. Subprocesses
are **not** a sandbox. The host does not install packages during discovery.
Install commands require explicit confirmation unless `--yes` is passed.
Argv are passed as separate process arguments (never a shell string).
