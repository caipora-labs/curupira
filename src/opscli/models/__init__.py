"""Typed contracts exported for adapters and application consumers."""

from opscli.models.configuration import (
    AutomationConfiguration,
    CodingAgentDefaults,
    CodingAgentsSettings,
    CronAutomationConfiguration,
    ExecutionSettings,
    IssueAutomationConfiguration,
    PollingSettings,
    PullRequestAutomationConfiguration,
)
from opscli.models.github import (
    DEFAULT_ISSUE_JSON_FIELDS,
    GhIssue,
    GhIssueSearchRequest,
    GhLabel,
    GhPullRequest,
    GhPullRequestSearchRequest,
    GhRepositoryCheckout,
    GhRepositoryCloneRequest,
)
from opscli.models.process import (
    CodingTaskRequest,
    CommandRequest,
    DispatchOutcome,
    ProcessResult,
)
from opscli.models.profiles import (
    ClaudeCodeCliProfile,
    CliProfile,
    CodexCliProfile,
    CursorCliProfile,
    OpenCodeCliProfile,
)
from opscli.models.tasks import (
    CronRunState,
    ResolvedAutomation,
    RunningCodingSession,
    Task,
    TaskIdentity,
)

__all__ = [
    "DEFAULT_ISSUE_JSON_FIELDS",
    "AutomationConfiguration",
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
    "GhLabel",
    "GhPullRequest",
    "GhPullRequestSearchRequest",
    "GhRepositoryCheckout",
    "GhRepositoryCloneRequest",
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
