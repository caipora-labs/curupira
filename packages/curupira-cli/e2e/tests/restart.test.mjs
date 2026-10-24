// Restarting Curupira in the middle of a task continues the coding agent's session: the only
// task state Curupira keeps is the session id of work that has not finished.

import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { createWorkspace, launch, waitForDashboard } from "../lib/harness.mjs";

const MINUTE = 75_000;

test("a restart continues the agent session of an unfinished task", { timeout: 180_000 }, async (t) => {
  const workspace = createWorkspace({ live: ["qa-slow"] });
  t.after(() => workspace.dispose());
  const session = (terminal) =>
    terminal
      .getByText("REPOSITORIES")
      .getByText("qa-slow", { direction: "after" })
      .or(terminal.getByText("REPOSITORIES").getByText("Tarefa longa", { direction: "after" }));

  // First run: the fake agent starts the task and keeps working for 30 s.
  const first = await launch(workspace, { name: "restart-first", cols: 140, rows: 40 });
  t.after(() => first.closeQuiet());
  await waitForDashboard(first);
  await first.getByText("started  qa-slow").wait({ timeout: MINUTE });
  await session(first).first().click();
  await first.getByText("opencode: Analisando a tarefa de teste.").wait({ timeout: 10_000 });
  const sessions = readdirSync(join(workspace.env.HOME, ".fake-opencode"));
  assert.equal(sessions.length, 1, "the agent opened one session");
  const [agentSession] = sessions;

  // Crash: no chance to clean up or to wait for the agent.
  await first.signal("KILL");
  await first.waitExit({ timeout: 10_000 });

  // Second run: the unfinished task comes back and the agent continues the same session.
  const second = await launch(workspace, { name: "restart-second", cols: 140, rows: 40 });
  t.after(() => second.closeQuiet());
  await waitForDashboard(second);
  await session(second).first().wait({ timeout: 30_000 });
  await session(second).first().click();
  await second
    .getByText(`opencode: Continuando a sessão ${agentSession} com as instruções da tarefa.`)
    .wait({ timeout: 30_000 });
  await second.getByText("Task finished.").wait({ timeout: 15_000 });
  assert.deepEqual(
    readdirSync(join(workspace.env.HOME, ".fake-opencode")),
    [agentSession],
    "no new agent session was opened",
  );
});
