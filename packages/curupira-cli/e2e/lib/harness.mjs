// Sandboxed runs of `curupira tui` for @microsoft/tui-test.
//
// Every workspace gets its own HOME, state database, local bare Git repository, and a fake
// `opencode` on PATH, so tests never touch ~/.curupira, the network, or a real coding agent.

import { execFileSync } from "node:child_process";
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { TuiTest } from "@microsoft/tui-test";

const here = dirname(fileURLToPath(import.meta.url));
export const ARTIFACTS = resolve(here, "..", "artifacts");

/** The binary under test: CURUPIRA_BIN, or the debug build of this crate. */
export const BIN = process.env.CURUPIRA_BIN ?? resolve(here, "..", "..", "target", "debug", "curupira");

/** Automations whose cron fires every minute; the prompt marker picks the fake agent's behavior. */
export const LIVE_AUTOMATIONS = {
  "qa-ok": "Review the repository. SCENARIO:ok",
  "qa-fail": "Review the repository. SCENARIO:fail",
  "qa-noise": "Review the repository. SCENARIO:noise",
  "qa-slow": "Review the repository. SCENARIO:slow",
};

function git(cwd, ...args) {
  execFileSync("git", args, { cwd, stdio: "ignore" });
}

function settings(root, live) {
  const ids = live === true ? Object.keys(LIVE_AUTOMATIONS).filter((id) => id !== "qa-slow") : live || [];
  const automations = ids.length
    ? ids.map((id) => [id, LIVE_AUTOMATIONS[id]]).map(
        ([id, prompt]) => `
[automations.${id}]
trigger_type = "cron"
repository = "demo"
schedule = "* * * * *"
prompt = "${prompt}"
`,
      )
    : [
        `
# Starts in 2030, so nothing is dispatched.
[automations.idle]
trigger_type = "cron"
repository = "demo"
schedule = "0 9 * * 1"
start_date = 2030-01-01T00:00:00Z
prompt = "noop"
`,
      ];
  return `[settings]
max_active_tasks = 3
workspace_dir = "${join(root, "workspaces")}"
state_db_path = "${join(root, "state.sqlite3")}"
task_timeout_minutes = 1

[settings.polling]
poll_interval_seconds = 1
cron_poll_interval_seconds = 1

[repositories.demo]
remote = "${join(root, "repo.git")}"

[agents.defaults]
profile = "fake"
timezone = "UTC"

[agents.profiles.fake]
provider = "opencode"
api = "v2"
model = "test/model"

[assistant]
agent = "opencode"
${automations.join("")}`;
}

/**
 * A throwaway Curupira home. `live` adds cron automations that dispatch the fake agent at the
 * next minute boundary: `true` for all of LIVE_AUTOMATIONS except `qa-slow` (only restart tests
 * need it), or a list of their ids.
 */
export function createWorkspace({ live = false } = {}) {
  if (!existsSync(BIN)) {
    throw new Error(`${BIN} not found: run \`cargo build --bin curupira\` first or set CURUPIRA_BIN`);
  }
  const root = mkdtempSync(join(tmpdir(), "curupira-tui-"));
  const home = join(root, "home");
  const bin = join(root, "bin");
  mkdirSync(home);
  mkdirSync(bin);

  const source = join(root, "repo-src");
  mkdirSync(source);
  git(source, "init", "-q", "-b", "main");
  git(source, "-c", "user.email=qa@example.test", "-c", "user.name=qa", "commit", "-q", "--allow-empty", "-m", "init");
  git(root, "clone", "-q", "--bare", source, join(root, "repo.git"));

  copyFileSync(join(here, "fake-opencode.sh"), join(bin, "opencode"));
  chmodSync(join(bin, "opencode"), 0o755);

  const config = join(root, "settings.toml");
  writeFileSync(config, settings(root, live));
  return {
    root,
    config,
    env: { HOME: home, PATH: `${bin}:${process.env.PATH}`, TERM: "xterm-256color" },
    dispose: () => rmSync(root, { recursive: true, force: true }),
  };
}

/**
 * Start `curupira tui` in a fresh emulator. Traces of failed operations land in
 * artifacts/traces (open trace.html in a browser; trace.md is the text summary).
 */
export async function launch(workspace, { cols = 120, rows = 36, name = "tui" } = {}) {
  const terminal = TuiTest.ephemeral(`curupira-${name}`, {
    trace: { mode: "on-failure", directory: join(ARTIFACTS, "traces") },
    artifacts: { dir: join(ARTIFACTS, "failures"), onFailure: "all" },
  });
  await terminal.run(BIN, ["--config", workspace.config, "tui"], {
    cols,
    rows,
    env: workspace.env,
    waitReady: false,
  });
  return terminal;
}

/** Wait until the splash has given way to the dashboard. */
export async function waitForDashboard(terminal, timeout = 10_000) {
  await terminal.getByText("REPOSITORIES").wait({ timeout });
}
