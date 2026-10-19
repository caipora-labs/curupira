import assert from "node:assert/strict";
import { test } from "node:test";

import { createWorkspace, launch, waitForDashboard } from "../lib/harness.mjs";

async function dashboard(t, name, size) {
  const workspace = createWorkspace();
  const terminal = await launch(workspace, { name, ...size });
  t.after(async () => {
    await terminal.closeQuiet();
    workspace.dispose();
  });
  await waitForDashboard(terminal);
  return terminal;
}

test("tab moves focus between the input and the sidebar", async (t) => {
  const terminal = await dashboard(t, "focus");
  await terminal.getByText("enter send").expect();
  await terminal.press("Tab");
  await terminal.getByText("↑↓ select").wait({ timeout: 2_000 });
  await terminal.press("Tab");
  await terminal.getByText("enter send").wait({ timeout: 2_000 });
});

test("clicking the input focuses it, and a submitted message is recorded as not sent", async (t) => {
  const terminal = await dashboard(t, "input");
  await terminal.press("Tab");
  await terminal.getByText("↑↓ select").wait({ timeout: 2_000 });

  await terminal.getByText("Message the default agent").click();
  await terminal.getByText("enter send").wait({ timeout: 2_000 });
  await terminal.type("hello agent");
  await terminal.getByText("curupira > hello agent").wait({ timeout: 2_000 });
  await terminal.press("Enter");

  await terminal.getByText("Not sent: agent sessions are not connected to the TUI yet.").wait({ timeout: 2_000 });
  await terminal.getByText("Message the default agent").expect();
});

test("letters typed into the input never trigger shortcuts", async (t) => {
  const terminal = await dashboard(t, "shortcuts");
  await terminal.type("hq");
  await terminal.getByText("curupira > hq").wait({ timeout: 2_000 });
  await terminal.getByText("DEFAULT AGENT").expect();
});

test("the layout follows resizes down to the too-small notice and back", async (t) => {
  const terminal = await dashboard(t, "resize");
  await terminal.resize(80, 24);
  await terminal.getByText("SESSIONS").wait({ timeout: 2_000 });
  await terminal.resize(40, 10);
  await terminal.getByText("Terminal too small").wait({ timeout: 2_000 });
  await terminal.resize(120, 36);
  await terminal.getByText("SESSIONS").wait({ timeout: 2_000 });
});

test("escape quits with status 0 and restores the terminal", async (t) => {
  const terminal = await dashboard(t, "quit");
  await terminal.press("Escape");
  await terminal.waitExit({ timeout: 10_000 });
  const state = await terminal.state();
  assert.equal(state.exited, 0, "exit status");
  assert.equal(state.modes.alternate_screen, false);
  assert.equal(state.mouse_mode, "none");
  assert.equal(state.modes.cursor_visible, true);
});
