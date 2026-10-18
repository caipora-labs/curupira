import { defineTriggers } from "@caipora/curupira-sdk";

/**
 * Example trigger documented with JSDoc for editor autocomplete.
 *
 * @typedef {Object} GitHubIssueParams
 * @property {string} repo
 * @property {string[]} [labels]
 */

/**
 * @param {GitHubIssueParams} params
 */
async function githubIssue({ repo, labels = [] }) {
  if (repo === "empty/repo") {
    return null;
  }
  return {
    repo,
    labels,
    title: "Fix authentication",
  };
}

export default defineTriggers({
  githubIssue,
});
