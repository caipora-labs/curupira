import { defineTriggers } from "@caipora-labs/curupira-sdk";

async function sampleTrigger({ note = "hi" }) {
  if (note === "skip") {
    return null;
  }
  return { note, ready: true };
}

function syncTrigger() {
  return { kind: "sync" };
}

export default defineTriggers({
  sampleTrigger,
  syncTrigger,
});
