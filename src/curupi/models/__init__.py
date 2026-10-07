"""Typed contracts exported for adapters and application consumers."""

from curupi.models.configuration import (
    AutomationConfiguration,
    CodingAgentDefaults,
    CodingAgentsSettings,
    CronAutomationConfiguration,
    ExecutionSettings,
    IssueAutomationConfiguration,
    PollingSettings,
    PullRequestAutomationConfiguration,
)
from curupi.models.github import (
    DEFAULT_ISSUE_JSON_FIELDS,
    GhIssue,
    GhIssueSearchRequest,
    GhLabel,
    GhPullRequest,
    GhPullRequestSearchRequest,
)
from curupi.models.process import (
    CodingTaskRequest,
    CommandRequest,
    DispatchOutcome,
    ProcessResult,
)
from curupi.models.profiles import (
    ClaudeCodeCliProfile,
    CliProfile,
    CodexCliProfile,
    CursorCliProfile,
    OpenCodeCliProfile,
)
from curupi.models.tasks import (
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
