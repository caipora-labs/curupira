import { defineTriggers } from "@caipora/curupira-sdk";

export default defineTriggers({
  githubIssue: async (params: { repo: string; labels?: string[] }) => {
    if (params.repo === "empty/repo") {
      return null;
    }
    return {
      repo: params.repo,
      labels: params.labels ?? [],
      title: "Fix authentication",
    };
  },
});
