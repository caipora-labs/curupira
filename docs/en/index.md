# OpsCli

OpsCli runs automations on your machine. It takes a GitHub issue or pull request, or a local cron occurrence, and hands it to a coding-agent CLI you already have.

Each automation in the settings TOML watches one source and carries its own prompt. All automations share one discovery, scheduling, and execution pipeline: `run` executes a single currently available task, while `watch` polls every automation continuously.

## Get started

1. [Install OpsCli and its requirements](installation.md).
2. [Configure automations](configuration.md) for issues, pull requests, or cron.
3. [Validate and run](operations.md) your configuration.

See [providers and agents](providers.md) for provider-native options and session resumption.
