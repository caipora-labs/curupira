"""Issue selection and dispatch orchestration."""

from __future__ import annotations

from pathlib import Path
from string import Template

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.coding_agents import (
    RESUME_SESSION_PROMPT,
    CodingAgentFactory,
    create_coding_agent,
    resolve_coding_agent_profile,
)
from gh_dispatch.config import AppSettings
from gh_dispatch.errors import PromptRenderError
from gh_dispatch.models import (
    AgentSettings,
    CodingTaskRequest,
    DispatchOutcome,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
    GhRepositoryCloneRequest,
    PromptContext,
    RepositorySettings,
    RunningCodingSession,
    SelectedTask,
)
from gh_dispatch.repositories import RunningSessionRepository

DEFAULT_PULL_REQUEST_PROMPT = """Work on pull request ${pull_request_number}: ${pull_request_title}

${pull_request_body}

Repository: ${repo}
URL: ${pull_request_url}
Head: ${pull_request_head_ref}
Base: ${pull_request_base_ref}
"""


async def select_next_issue(settings: AppSettings, gh: GhClient) -> SelectedTask | None:
    """Return the first matching issue, respecting TOML repository order."""
    for repository in settings.watchers.issues.repositories:
        issues = await gh.list_issues(
            GhIssueSearchRequest(
                repo=repository.repo,
                query=repository.query,
                limit=1,
            )
        )
        if issues:
            issue = issues[0]
            return SelectedTask(
                task_type="issue",
                repository=repository,
                number=issue.number,
                title=issue.title,
                body=issue.body,
                url=issue.url,
                workspace_path=repository.workspace_path(settings.core.workspace_dir),
            )
    return None


async def select_next_pull_request(
    settings: AppSettings,
    gh: GhClient,
) -> SelectedTask | None:
    """Return the first matching pull request in TOML repository order."""
    watcher = settings.watchers.pull_requests
    if watcher is None:
        return None
    for repository in watcher.repositories:
        pull_requests = await gh.list_pull_requests(
            GhPullRequestSearchRequest(
                repo=repository.repo,
                query=repository.query,
                limit=1,
            )
        )
        if pull_requests:
            return _select_pull_request(
                repository,
                pull_requests[0],
                settings.core.workspace_dir,
            )
    return None


def _select_pull_request(
    repository: RepositorySettings,
    pull_request: GhPullRequest,
    workspace_dir: Path,
) -> SelectedTask:
    return SelectedTask(
        task_type="pull_request",
        repository=repository,
        number=pull_request.number,
        title=pull_request.title,
        body=pull_request.body,
        url=pull_request.url,
        workspace_path=repository.workspace_path(workspace_dir),
        is_draft=pull_request.is_draft,
        head_ref_name=pull_request.head_ref_name,
        base_ref_name=pull_request.base_ref_name,
    )


def render_prompt(settings: AppSettings, selected: SelectedTask) -> str:
    """Render the task prompt and compatibility aliases for issue/PR templates."""
    return render_task_prompt(settings.agent, selected)


def render_task_prompt(agent: AgentSettings, selected: SelectedTask) -> str:
    """Render a task using the global or repository-specific prompt."""
    is_pull_request = selected.task_type == "pull_request"
    is_issue = selected.task_type == "issue"
    if selected.repository.prompt is not None:
        template_text = selected.repository.prompt
    elif is_pull_request:
        template_text = agent.pull_request_prompt or DEFAULT_PULL_REQUEST_PROMPT
    else:
        template_text = agent.prompt
    number = str(selected.number)
    title = selected.title
    body = selected.body or ""
    url = selected.url
    context = PromptContext(
        repo=selected.repository.repo,
        issue_number=number if is_issue else "",
        issue_title=title if is_issue else "",
        issue_body=body if is_issue else "",
        issue_url=url if is_issue else "",
        pull_request_number=number if is_pull_request else "",
        pull_request_title=title if is_pull_request else "",
        pull_request_body=body if is_pull_request else "",
        pull_request_url=url if is_pull_request else "",
        pull_request_is_draft=(
            str(selected.is_draft).lower()
            if is_pull_request and selected.is_draft is not None
            else ""
        ),
        pull_request_head_ref=selected.head_ref_name or "" if is_pull_request else "",
        pull_request_base_ref=selected.base_ref_name or "" if is_pull_request else "",
        task_type=selected.task_type,
        task_number=number,
        task_title=title,
        task_body=body,
        task_url=url,
    )
    try:
        return Template(template_text).substitute(
            **{key: str(value) for key, value in context.model_dump().items()}
        )
    except (KeyError, ValueError) as error:
        raise PromptRenderError(f"could not render prompt: {error}") from error


async def dispatch_next_issue(
    settings: AppSettings,
    gh: GhClient,
    *,
    dry_run: bool = False,
    agent_factory: CodingAgentFactory = create_coding_agent,
    session_repository: RunningSessionRepository | None = None,
) -> DispatchOutcome:
    """Find one issue and optionally start its configured coding agent."""
    selected = await select_next_issue(settings, gh)
    return await _dispatch_selected_task(
        settings,
        gh,
        selected,
        dry_run=dry_run,
        agent_factory=agent_factory,
        session_repository=session_repository,
    )


async def dispatch_next_pull_request(
    settings: AppSettings,
    gh: GhClient,
    *,
    dry_run: bool = False,
    agent_factory: CodingAgentFactory = create_coding_agent,
    session_repository: RunningSessionRepository | None = None,
) -> DispatchOutcome:
    selected = await select_next_pull_request(settings, gh)
    return await _dispatch_selected_task(
        settings,
        gh,
        selected,
        dry_run=dry_run,
        agent_factory=agent_factory,
        session_repository=session_repository,
    )


async def _dispatch_selected_task(
    settings: AppSettings,
    gh: GhClient,
    selected: SelectedTask | None,
    *,
    dry_run: bool,
    agent_factory: CodingAgentFactory,
    session_repository: RunningSessionRepository | None,
) -> DispatchOutcome:
    if selected is None or dry_run:
        return DispatchOutcome(selected=selected)

    resumed_session = (
        await session_repository.get(selected) if session_repository is not None else None
    )
    checkout = await gh.ensure_repository(
        GhRepositoryCloneRequest(
            repo=selected.repository.repo,
            destination=selected.workspace_path,
        )
    )
    if resumed_session is None:
        profile = resolve_coding_agent_profile(
            settings.coding_agents,
            selected.repository.coding_agent,
        )
        provider = profile.provider
        message = render_prompt(settings, selected)
        model, agent, effort = profile.model, profile.agent, profile.effort
        session_id = None
        stored_message = message
    else:
        provider = resumed_session.provider
        message = RESUME_SESSION_PROMPT
        model, agent, effort = (
            resumed_session.model,
            resumed_session.agent,
            resumed_session.effort,
        )
        session_id = resumed_session.session_id
        stored_message = resumed_session.message

    coding_agent = agent_factory(provider)
    request = CodingTaskRequest(
        cwd=checkout.path,
        message=message,
        model=model,
        agent=agent,
        effort=effort,
        session_id=session_id,
    )

    if session_repository is None:
        process = await coding_agent.run_task(request)
    else:

        async def persist_session(session_id: str) -> None:
            await session_repository.save(
                RunningCodingSession(
                    task=selected,
                    session_id=session_id,
                    message=stored_message,
                    provider=provider,
                    model=model,
                    agent=agent,
                    effort=effort,
                )
            )

        process = await coding_agent.run_task(request, on_session_started=persist_session)
        await session_repository.delete(selected)
    return DispatchOutcome(selected=selected, process=process)
