"""Typed contracts exported for adapters and application consumers.

Import contracts from ``curupira.models``; reusable validation primitives and the model
bases live in ``curupira.models.base``. Nested payload parts (labels, hypermedia links)
stay in their defining modules.
"""

from curupira.models.azure import AzPullRequest, AzPullRequestSearchRequest
from curupira.models.configuration import (
    AutomationConfiguration,
    AzurePullRequestAutomationConfiguration,
    CodingAgentDefaults,
    CodingAgentsSettings,
    CronAutomationConfiguration,
    ExecutionSettings,
    IssueAutomationConfiguration,
    PollingSettings,
    PullRequestAutomationConfiguration,
)
from curupira.models.github import (
    DEFAULT_ISSUE_JSON_FIELDS,
    GhIssue,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
)
from curupira.models.process import (
    CodingTaskRequest,
    CommandRequest,
    DispatchOutcome,
    ProcessResult,
)
from curupira.models.profiles import (
    ClaudeCodeCliProfile,
    CliProfile,
    CodexCliProfile,
    CursorCliProfile,
    OpenCodeCliProfile,
)
from curupira.models.tasks import (
    CronRunState,
    ResolvedAutomation,
    RunningCodingSession,
    Task,
    TaskIdentity,
)

__all__ = [
    "DEFAULT_ISSUE_JSON_FIELDS",
    "AutomationConfiguration",
    "AzPullRequest",
    "AzPullRequestSearchRequest",
    "AzurePullRequestAutomationConfiguration",
    "ClaudeCodeCliProfile",
    "CliProfile",
    "CodexCliProfile",
    "CodingAgentDefaults",
    "CodingAgentsSettings",
    "CodingTaskRequest",
    "CommandRequest",
    "CronAutomationConfiguration",
    "CronRunState",
    "CursorCliProfile",
    "DispatchOutcome",
    "ExecutionSettings",
    "GhIssue",
    "GhIssueSearchRequest",
    "GhPullRequest",
    "GhPullRequestSearchRequest",
    "IssueAutomationConfiguration",
    "OpenCodeCliProfile",
    "PollingSettings",
    "ProcessResult",
    "PullRequestAutomationConfiguration",
    "ResolvedAutomation",
    "RunningCodingSession",
    "Task",
    "TaskIdentity",
]
