import { SerializationError } from "./errors.js";

/** One protocol pair (`trigger/poll` `values` element). */
export type KeyValue = { key: string; value: string };

/**
 * Convert one trigger return value into protocol pairs, or `null`.
 *
 * `null` / `undefined` mean nothing was found. An empty object becomes `[]`
 * (an item with no pairs). Top-level arrays and scalars are rejected.
 */
export function serializeTriggerResult(
  value: unknown,
  { triggerName }: { triggerName: string },
): KeyValue[] | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (isMultiValue(value)) {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: must return one object or null, not a collection`,
    );
  }
  return toKeyValues(value, { triggerName });
}

/** Convert one plain object into string pairs (insertion order). */
export function toKeyValues(
  value: unknown,
  { triggerName }: { triggerName: string },
): KeyValue[] {
  const mapping = asMapping(value, triggerName);
  const seen = new Set<string>();
  const pairs: KeyValue[] = [];
  for (const [key, item] of Object.entries(mapping)) {
    if (item === undefined) {
      continue;
    }
    if (key === "" || key.includes("}") || key.includes("${")) {
      throw new SerializationError(
        `trigger ${JSON.stringify(triggerName)}: key ${JSON.stringify(key)} cannot be used as a template placeholder`,
      );
    }
    if (seen.has(key)) {
      throw new SerializationError(
        `trigger ${JSON.stringify(triggerName)}: duplicate key ${JSON.stringify(key)}`,
      );
    }
    seen.add(key);
    pairs.push({
      key,
      value: stringifyValue(item, { triggerName }),
    });
  }
  return pairs;
}

/** Render one field value as a string. Nested objects become compact JSON. */
export function stringifyValue(
  value: unknown,
  { triggerName }: { triggerName: string },
): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    rejectNonFinite(value, triggerName);
    return JSON.stringify(value);
  }
  if (value === null) {
    return "null";
  }
  try {
    const compatible = toJsonCompatible(value, {
      triggerName,
      seen: new WeakSet(),
    });
    return stringifySorted(compatible);
  } catch (err) {
    if (err instanceof SerializationError) {
      throw err;
    }
    const detail = err instanceof Error ? err.message : String(err);
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: value of type ${typeName(value)} is not serializable (${detail})`,
    );
  }
}

function stringifySorted(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stringifySorted(item)).join(",")}]`;
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  const body = keys
    .map((key) => `${JSON.stringify(key)}:${stringifySorted(obj[key])}`)
    .join(",");
  return `{${body}}`;
}

/** Convert a nested value to a JSON-compatible structure. */
export function toJsonCompatible(
  value: unknown,
  {
    triggerName,
    seen,
  }: { triggerName: string; seen: WeakSet<object> },
): unknown {
  if (typeof value === "string" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    rejectNonFinite(value, triggerName);
    return value;
  }
  if (value === null) {
    return null;
  }
  if (typeof value === "bigint") {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: value of type bigint is not serializable`,
    );
  }
  if (typeof value === "function" || typeof value === "symbol") {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: value of type ${typeof value} is not serializable`,
    );
  }
  if (typeof value !== "object") {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: value of type ${typeName(value)} is not serializable`,
    );
  }
  if (value instanceof Date) {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: value of type Date is not serializable`,
    );
  }
  if (ArrayBuffer.isView(value) || value instanceof ArrayBuffer) {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: value of type ${typeName(value)} is not serializable`,
    );
  }
  if (value instanceof Map || value instanceof Set) {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: value of type ${typeName(value)} is not serializable`,
    );
  }
  if (seen.has(value)) {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: circular structure is not serializable`,
    );
  }
  seen.add(value);
  if (Array.isArray(value)) {
    return value.map((item) => toJsonCompatible(item, { triggerName, seen }));
  }
  const out: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (item === undefined) {
      continue;
    }
    if (typeof key !== "string") {
      throw new SerializationError(
        `trigger ${JSON.stringify(triggerName)}: nested key ${JSON.stringify(key)} is not a string`,
      );
    }
    if (Object.hasOwn(out, key)) {
      throw new SerializationError(
        `trigger ${JSON.stringify(triggerName)}: duplicate nested key ${JSON.stringify(key)}`,
      );
    }
    out[key] = toJsonCompatible(item, { triggerName, seen });
  }
  return out;
}

function asMapping(
  value: unknown,
  triggerName: string,
): Record<string, unknown> {
  if (
    typeof value === "string" ||
    typeof value === "boolean" ||
    typeof value === "number" ||
    typeof value === "bigint"
  ) {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: return value must be an object, not ${typeName(value)}`,
    );
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: return value of type ${typeName(value)} is not an object`,
    );
  }
  if (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null) {
    // Allow class instances that are plain data bags (own enumerable props only).
    // Reject exotic built-ins already handled above.
  }
  return value as Record<string, unknown>;
}

function rejectNonFinite(value: number, triggerName: string): void {
  if (!Number.isFinite(value)) {
    throw new SerializationError(
      `trigger ${JSON.stringify(triggerName)}: non-finite number ${String(value)} is not serializable`,
    );
  }
}

function isMultiValue(value: unknown): boolean {
  if (Array.isArray(value)) {
    return true;
  }
  if (value instanceof Set || value instanceof Map) {
    return true;
  }
  return typeof value === "object" && value !== null && Symbol.iterator in value
    ? !(value instanceof String)
    : false;
}

function typeName(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return "Array";
  }
  if (typeof value === "object") {
    const name = value.constructor?.name;
    return name && name !== "Object" ? name : "object";
  }
  return typeof value;
}

/** Compact JSON with sorted keys (matches the Python SDK nested encoding). */
export function compactJson(value: unknown): string {
  return stringifySorted(value);
}
