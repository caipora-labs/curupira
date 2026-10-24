// Drive `curupira tui` step by step and keep what the screen showed after each step.
//
//   npm run inspect -- [--live] [--config PATH] [--size 120x36] [--step STEP ...]
//
// Without --config the TUI runs in a sandbox (temporary HOME, fake `opencode` agent, no network);
// --live adds cron automations that dispatch the fake agent at the next minute. With --config the
// real settings are used: real automations run and real agents are started.
//
// Steps run in order:
//   wait:TEXT        wait until TEXT is on screen (up to 90 s)
//   gone:TEXT        wait until TEXT is no longer on screen
//   click:TEXT       click the first match of TEXT
//   session:NAME     click the sidebar session NAME (Home may show the same text)
//   key:KEY          press a key (Tab, Enter, Escape, Up, Down, Ctrl+L, h, ...)
//   type:TEXT        type TEXT
//   sleep:MS         wait MS milliseconds
//   resize:COLSxROWS resize the terminal
//   shot:NAME        save NAME.txt and NAME.svg (every step also saves one automatically)
//
// Output: artifacts/inspect/NN-<step>.{txt,svg}; the text is also printed.

import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { parseArgs } from "node:util";

import { ARTIFACTS, createWorkspace, launch } from "../lib/harness.mjs";

const { values } = parseArgs({
  options: {
    live: { type: "boolean", default: false },
    config: { type: "string" },
    size: { type: "string", default: "120x36" },
    step: { type: "string", multiple: true, default: [] },
  },
});

const [cols, rows] = values.size.split("x").map(Number);
const out = join(ARTIFACTS, "inspect");
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

const workspace = values.config
  ? { config: values.config, env: { TERM: "xterm-256color" }, dispose: () => {} }
  : createWorkspace({ live: values.live });
const terminal = await launch(workspace, { name: "inspect", cols, rows });

let count = 0;
async function capture(label) {
  count += 1;
  const name = `${String(count).padStart(2, "0")}-${label.replace(/[^a-z0-9]+/gi, "-").slice(0, 40)}`;
  const text = await terminal.text();
  writeFileSync(join(out, `${name}.txt`), text);
  await terminal.screenshot(join(out, `${name}.svg`));
  console.log(`\n===== ${name} =====\n${text}`);
}

async function run(step) {
  const [kind, ...rest] = step.split(":");
  const arg = rest.join(":");
  switch (kind) {
    case "wait":
      return terminal.getByText(arg).wait({ timeout: 90_000 });
    case "gone":
      return terminal.getByText(arg).wait({ state: "hidden", timeout: 90_000 });
    case "click":
      return terminal.getByText(arg).first().click();
    case "session":
      return terminal.getByText("REPOSITORIES").getByText(arg, { direction: "after" }).first().click();
    case "key":
      return terminal.press(arg);
    case "type":
      return terminal.type(arg);
    case "sleep":
      return new Promise((done) => setTimeout(done, Number(arg)));
    case "resize": {
      const [c, r] = arg.split("x").map(Number);
      return terminal.resize(c, r);
    }
    case "shot":
      return undefined;
    default:
      throw new Error(`unknown step ${step}`);
  }
}

try {
  await terminal.getByText("REPOSITORIES").wait({ timeout: 10_000 });
  await capture("dashboard");
  for (const step of values.step) {
    try {
      await run(step);
    } catch (error) {
      console.error(`step ${step} failed: ${error.message.split("\n")[0]}`);
      await capture(`failed-${step}`);
      process.exitCode = 1;
      break;
    }
    await capture(step);
  }
} finally {
  await terminal.closeQuiet();
  workspace.dispose();
  console.log(`\nScreens saved in ${out}`);
}
