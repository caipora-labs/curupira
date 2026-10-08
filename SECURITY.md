# Security Policy

## Supported versions

Only the latest released version of Curupira receives security fixes.

## Reporting a vulnerability

Open a GitHub Security Advisory on this repository
(`Security` → `Advisories` → `New draft advisory`) or, if that is unavailable,
open a minimal issue titled "Security report" with no exploit details and request a
private contact channel. Please include the Curupira version, the provider CLI in
use, and steps to reproduce.

We aim to acknowledge reports within 7 days and will coordinate a fix and release
before any public disclosure.

## Scope

In scope: command construction for provider CLIs and `gh` (argument injection,
shell-escape flaws), prompt/state handling that could leak credentials across
automations, and unsafe handling of the local state database.

Out of scope: vulnerabilities in the provider CLIs themselves (`opencode`, `codex`,
`claude`, `agent`, `gh`), in GitHub, or in the repositories the agents check out.
Curupira executes prompts with local CLIs that can read and modify your
checkouts — review automation prompts and only run automations you trust.
