import { RegistrationError } from "./errors.js";

/**
 * Convert a JS identifier (camelCase, snake_case, or kebab-case) to a local
 * trigger name in kebab-case (`githubIssue` → `github-issue`).
 */
export function toKebabCase(name: string): string {
  if (!name) {
    throw new RegistrationError("trigger name must not be empty");
  }
  const withHyphens = name
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/_/g, "-")
    .replace(/-+/g, "-")
    .toLowerCase();
  return validateTriggerLocalName(withHyphens);
}

/** Accept a kebab-case local trigger name (no slash). */
export function validateTriggerLocalName(name: string): string {
  if (!name) {
    throw new RegistrationError("trigger name must not be empty");
  }
  if (name.includes("/")) {
    throw new RegistrationError(
      `trigger name ${JSON.stringify(name)} must not contain '/'; ` +
        "the host prefixes the [plugins.<alias>] registration name",
    );
  }
  if (name.startsWith("-") || name.endsWith("-") || name.includes("--")) {
    throw new RegistrationError(
      `trigger name ${JSON.stringify(name)} is not valid kebab-case`,
    );
  }
  if (![...name].every((c) => /[a-z0-9-]/.test(c))) {
    throw new RegistrationError(
      `trigger name ${JSON.stringify(name)} is not valid kebab-case`,
    );
  }
  if (![...name].some((c) => /[a-z]/.test(c))) {
    throw new RegistrationError(
      `trigger name ${JSON.stringify(name)} is not valid kebab-case`,
    );
  }
  return name;
}
