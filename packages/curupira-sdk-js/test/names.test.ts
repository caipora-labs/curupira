import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { RegistrationError } from "../dist/errors.js";
import { toKebabCase, validateTriggerLocalName } from "../dist/names.js";

describe("toKebabCase", () => {
  it("converts camelCase and snake_case", () => {
    assert.equal(toKebabCase("githubIssue"), "github-issue");
    assert.equal(toKebabCase("github_issues"), "github-issues");
    assert.equal(toKebabCase("github-issues"), "github-issues");
  });

  it("rejects empty and invalid names", () => {
    assert.throws(() => toKebabCase(""), RegistrationError);
    assert.throws(() => validateTriggerLocalName("a/b"), /must not contain/);
    assert.throws(() => validateTriggerLocalName("-x"), RegistrationError);
    assert.throws(() => validateTriggerLocalName("123"), RegistrationError);
  });
});
