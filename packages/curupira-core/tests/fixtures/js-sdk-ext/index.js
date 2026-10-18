import { defineTriggers } from "@caipora/curupira-sdk";

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
