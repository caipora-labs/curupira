// Live dispatch: cron automations fire at the next minute boundary and run the fake agent,
// so this file takes up to about a minute and a half.

import { test } from "node:test";

import { createWorkspace, launch, waitForDashboard } from "../lib/harness.mjs";

const MINUTE = 75_000;

async function start(t, live, name) {
  const workspace = createWorkspace({ live });
  const terminal = await launch(workspace, { name, cols: 140, rows: 40 });
  t.after(async () => {
    await terminal.closeQuiet();
    workspace.dispose();
  });
  await waitForDashboard(terminal);
  return terminal;
}

test("dispatched tasks appear as live sessions with their agent output", { timeout: 180_000 }, async (t) => {
  // Both dashboards wait for the same minute boundary.
  const [terminal, noisy] = await Promise.all([
    start(t, ["qa-ok", "qa-fail"], "sessions"),
    start(t, ["qa-noise"], "noise"),
  ]);
  const session = (name) => terminal.getByText("REPOSITORIES").getByText(name, { direction: "after" });
  const titled = "Revisão automática do repositório";
  // The narrow sidebar truncates long titles; the header shows them in full.
  const shown = "Revisão automática";
  await session("qa-ok").or(session(shown)).wait({ timeout: MINUTE });

  await t.test("a session takes the title its coding agent gave it", async () => {
    await session(shown).wait({ timeout: 10_000 });
    await session("qa-ok").expect({ not: true });
  });

  await t.test("a session the agent never titled keeps the task's name", async () => {
    await session("qa-fail").wait({ timeout: 5_000 });
  });

  await t.test("attaching shows the prompt and the agent's text and tools as they arrive", async () => {
    await session(shown).click();
    await terminal.getByText(`ATTACHED: ${titled} - opencode · test/model`).wait({ timeout: 2_000 });
    await terminal.getByText("Automation qa-ok").expect();
    await terminal.getByText("Review the repository. SCENARIO:ok").expect();
    await terminal.getByText("opencode: Analisando a tarefa de teste.").wait({ timeout: 5_000 });
    await terminal.getByText("▸ shell  gh pr checks 1").expect();
    await terminal.getByText("opencode: Tudo certo, nada a fazer.").wait({ timeout: 15_000 });
    await terminal.getByText("Task finished.").wait({ timeout: 5_000 });
  });

  await t.test("a failing agent shows its own error, not an empty message", async () => {
    await session("qa-fail").click();
    await terminal.getByText("ATTACHED: qa-fail - opencode · test/model").wait({ timeout: 2_000 });
    await terminal.getByText("✗ Model unavailable: test/model").wait({ timeout: 5_000 });
    await terminal.getByText("agent exited 1: Model unavailable: test/model").wait({ timeout: 5_000 });
  });

  await t.test("Home lists every task by title", async () => {
    await terminal.getByText("[ Home ]").click();
    await terminal.getByText("DEFAULT AGENT").wait({ timeout: 2_000 });
    await terminal.getByText(`done  ${titled}`).expect();
    await terminal.getByText("failed  qa-fail").expect();
  });

  await t.test("text an agent writes straight to the terminal is repainted away", async () => {
    await noisy.getByText("NOISE-FROM-AGENT").wait({ timeout: MINUTE });
    await noisy.getByText("done  Agente que escreve no terminal").wait({ timeout: 15_000 });
    await noisy.getByText("NOISE-FROM-AGENT").expect({ not: true });
  });
});
