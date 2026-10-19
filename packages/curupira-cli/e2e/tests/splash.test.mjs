import { execFileSync } from "node:child_process";
import { test } from "node:test";

import { BIN, createWorkspace, launch, waitForDashboard } from "../lib/harness.mjs";

const TAGLINE = "Local automations for coding agents";

test("the splash gives way to a dashboard with nothing left behind", async (t) => {
  const workspace = createWorkspace();
  const terminal = await launch(workspace, { name: "splash" });
  t.after(async () => {
    await terminal.closeQuiet();
    workspace.dispose();
  });

  await terminal.getByText(TAGLINE).wait({ timeout: 5_000 });
  await waitForDashboard(terminal);
  await terminal.getByText(TAGLINE).expect({ not: true });
  await terminal.getByText("DEFAULT AGENT").expect();
  await terminal.getByText("No sessions yet.").expect();
  await terminal.getByText("Tasks appear here.").expect();
});

test("any key skips the splash", async (t) => {
  const workspace = createWorkspace();
  const terminal = await launch(workspace, { name: "splash-skip" });
  t.after(async () => {
    await terminal.closeQuiet();
    workspace.dispose();
  });

  await terminal.getByText(TAGLINE).wait({ timeout: 5_000 });
  await terminal.press("Space");
  await waitForDashboard(terminal, 1_000);
});

test("the splash and the sidebar show the version the binary reports", async (t) => {
  // `curupira --version` prints the full version; the screen drops the commit hash.
  const full = execFileSync(BIN, ["--version"], { encoding: "utf8" }).trim().replace(/^curupira /, "");
  const shown = `v${full.split(".g")[0]}`;
  const workspace = createWorkspace();
  const terminal = await launch(workspace, { name: "version" });
  t.after(async () => {
    await terminal.closeQuiet();
    workspace.dispose();
  });

  await terminal.getByText(`${TAGLINE}  ·  ${shown}`).wait({ timeout: 5_000 });
  await waitForDashboard(terminal);
  await terminal.getByText(shown).expect();
});
