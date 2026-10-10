"""Compatibility re-export of the GitHub GraphQL discovery client."""

from curupira.clients.github_graphql import GitHubGraphQLClient as GhClient
from curupira.clients.github_graphql import GitHubGraphQLClient as GitHubGraphQLClient

__all__ = ["GhClient", "GitHubGraphQLClient"]
