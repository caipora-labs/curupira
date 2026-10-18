import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { defineTriggers, isDefinedTriggers } from "../dist/defineTriggers.js";
import { RegistrationError } from "../dist/errors.js";

describe("defineTriggers", () => {
  it("registers property names as kebab-case local triggers", () => {
    async function githubIssue() {
      return null;
    }
    const defined = defineTriggers({
      githubIssue,
      syncProbe: () => ({ ok: true }),
    });
    assert.equal(isDefinedTriggers(defined), true);
    assert.deepEqual(
      defined.registrations.map((entry) => entry.localName),
      ["github-issue", "sync-probe"],
    );
    assert.equal(defined.registrations[0]?.propertyName, "githubIssue");
    assert.equal(defined.triggers.githubIssue, githubIssue);
  });

  it("supports anonymous functions and object methods", () => {
    const defined = defineTriggers({
      alpha: async () => ({ n: 1 }),
      beta() {
        return { n: 2 };
      },
    });
    assert.equal(defined.registrations.length, 2);
    assert.equal(defined.registrations[0]?.localName, "alpha");
    assert.equal(defined.registrations[1]?.localName, "beta");
  });

  it("rejects empty maps and non-functions", () => {
    assert.throws(() => defineTriggers({}), /at least one/);
    assert.throws(
      () => defineTriggers({ bad: 1 as unknown as () => null }),
      RegistrationError,
    );
  });

  it("rejects duplicate kebab-case names", () => {
    assert.throws(
      () =>
        defineTriggers({
          githubIssue: () => null,
          github_issue: () => null,
        }),
      /duplicate trigger name/,
    );
  });
});
