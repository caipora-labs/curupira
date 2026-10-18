/**
 * Fixture used to document JSDoc parameter typing for editors.
 * Executable so integration tests can speak the protocol with it.
 */

import { defineTriggers, runExtension } from "../../dist/index.js";

/**
 * @typedef {Object} GitHubIssueParams
 * @property {string} repo
 * @property {string[]} [labels]
 */

/**
 * Busca issues de um repositório.
 *
 * @param {GitHubIssueParams} params
 */
async function githubIssue({ repo, labels = [] }) {
  return {
    repo,
    labels,
  };
}

const triggers = defineTriggers({
  githubIssue,
});

export default triggers;

await runExtension(triggers, {
  name: "example-jsdoc",
  version: "0.0.0",
});
