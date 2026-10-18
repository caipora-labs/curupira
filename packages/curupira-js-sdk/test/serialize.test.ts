import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { SerializationError } from "../dist/errors.js";
import { serializeTriggerResult } from "../dist/serialize.js";

describe("serializeTriggerResult", () => {
  it("returns null for nullish", () => {
    assert.equal(serializeTriggerResult(null, { triggerName: "t" }), null);
    assert.equal(serializeTriggerResult(undefined, { triggerName: "t" }), null);
  });

  it("converts objects to key/value string pairs", () => {
    assert.deepEqual(
      serializeTriggerResult(
        {
          repository: "acme/api",
          title: "Fix authentication",
          labels: ["bug", "security"],
          ready: true,
          count: 2,
          note: null,
        },
        { triggerName: "github-issue" },
      ),
      [
        { key: "repository", value: "acme/api" },
        { key: "title", value: "Fix authentication" },
        { key: "labels", value: '["bug","security"]' },
        { key: "ready", value: "true" },
        { key: "count", value: "2" },
        { key: "note", value: "null" },
      ],
    );
  });

  it("treats empty objects as an item with no pairs", () => {
    assert.deepEqual(serializeTriggerResult({}, { triggerName: "t" }), []);
  });

  it("skips undefined own properties", () => {
    assert.deepEqual(
      serializeTriggerResult({ a: "1", b: undefined }, { triggerName: "t" }),
      [{ key: "a", value: "1" }],
    );
  });

  it("sorts nested object keys in compact JSON", () => {
    assert.deepEqual(
      serializeTriggerResult({ meta: { b: 1, a: 2 } }, { triggerName: "t" }),
      [{ key: "meta", value: '{"a":2,"b":1}' }],
    );
  });

  it("rejects collections and scalars", () => {
    assert.throws(
      () => serializeTriggerResult([{ a: 1 }], { triggerName: "t" }),
      /collection/,
    );
    assert.throws(
      () => serializeTriggerResult(42, { triggerName: "t" }),
      SerializationError,
    );
    assert.throws(
      () => serializeTriggerResult("x", { triggerName: "t" }),
      SerializationError,
    );
  });

  it("rejects bad keys and non-serializable values", () => {
    assert.throws(
      () => serializeTriggerResult({ "": "a" }, { triggerName: "t" }),
      /placeholder/,
    );
    assert.throws(
      () => serializeTriggerResult({ "a}": "b" }, { triggerName: "t" }),
      /placeholder/,
    );
    assert.throws(
      () => serializeTriggerResult({ "${a": "b" }, { triggerName: "t" }),
      /placeholder/,
    );
    assert.throws(
      () => serializeTriggerResult({ n: Number.NaN }, { triggerName: "t" }),
      /non-finite/,
    );
    assert.throws(
      () => serializeTriggerResult({ when: new Date() }, { triggerName: "t" }),
      /Date/,
    );
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    assert.throws(
      () => serializeTriggerResult(circular, { triggerName: "t" }),
      /circular/,
    );
  });
});
