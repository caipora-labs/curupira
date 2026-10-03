from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from gh_dispatch.config import AppSettings, load_settings


def write_config(path: Path, repository_path: Path, extra: str = "") -> Path:
    path.write_text(
        textwrap.dedent(
            f"""\
            [agent]
            prompt = "Issue ${{issue_number}}: ${{issue_title}}"

            [watchers.issues]
            poll_interval_seconds = 30
            batch_size = 30

            [[watchers.issues.repositories]]
            repo = "acme/api"
            path = "{repository_path}"
            query = "is:open label:ready sort:created-asc"
            {extra}
            """
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.asyncio
async def test_load_settings_from_toml(tmp_path: Path) -> None:
    repo_path = tmp_path / "checkout"
    repo_path.mkdir()
    config_path = write_config(tmp_path / "config.toml", repo_path)

    settings = await load_settings(config_path)

    assert settings.coding_agents.default == "opencode"
    assert settings.coding_agents.profiles["opencode"].provider == "opencode"
    assert settings.watchers.issues.repositories[0].repo == "acme/api"
    assert settings.watchers.issues.repositories[0].path == repo_path.resolve()
    assert settings.core.max_active_tasks == 1
    assert settings.watchers.issues.poll_interval_seconds == 30


@pytest.mark.asyncio
async def test_relative_repo_path_is_resolved_from_toml_directory(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    repo_path = config_dir / "checkout"
    config_dir.mkdir()
    repo_path.mkdir()
    config_path = write_config(tmp_path / "config" / "gh-dispatch.toml", Path("checkout"))

    settings = await load_settings(config_path)

    assert settings.watchers.issues.repositories[0].path == repo_path.resolve()


@pytest.mark.asyncio
async def test_missing_clone_uses_resolved_workspace_path_without_cloning(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "gh-dispatch.toml"
    config_path.write_text(
        '[core]\nworkspace_dir = "workspaces"\n\n'
        '[agent]\nprompt = "Fix ${issue_number}"\n\n'
        "[watchers.issues]\n\n"
        '[[watchers.issues.repositories]]\nrepo = "acme/api"\nquery = "is:open"\n',
        encoding="utf-8",
    )

    settings = await load_settings(config_path)
    repository = settings.watchers.issues.repositories[0]

    assert settings.core.workspace_dir == (config_dir / "workspaces").resolve()
    assert repository.path is None
    assert (
        repository.workspace_path(settings.core.workspace_dir)
        == (config_dir / "workspaces" / "acme" / "api").resolve()
    )
    assert not settings.core.workspace_dir.exists()


@pytest.mark.asyncio
async def test_relative_state_database_path_is_resolved_from_toml_directory(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "gh-dispatch.toml"
    config_path.write_text(
        '[core]\nstate_db_path = "state/local.sqlite3"\n\n'
        '[agent]\nprompt = "Fix ${issue_number}"\n\n'
        "[watchers.issues]\n\n"
        '[[watchers.issues.repositories]]\nrepo = "acme/api"\nquery = "is:open"\n',
        encoding="utf-8",
    )

    settings = await load_settings(config_path)

    assert settings.core.state_db_path == (config_dir / "state/local.sqlite3").resolve()


@pytest.mark.asyncio
async def test_toml_without_repo_path_is_valid_for_uncloned_repo(tmp_path: Path) -> None:
    config_path = tmp_path / "dispatch.toml"
    config_path.write_text(
        '[core]\nworkspace_dir = "workspace"\n\n'
        '[agent]\nprompt = "Fix ${issue_number}"\n\n'
        "[watchers.issues]\n\n"
        '[[watchers.issues.repositories]]\nrepo = "acme/new-repo"\nquery = "is:open"\n',
        encoding="utf-8",
    )

    settings = await load_settings(config_path)
    repository = settings.watchers.issues.repositories[0]

    assert repository.path is None
    assert (
        repository.workspace_path(settings.core.workspace_dir)
        == (tmp_path / "workspace" / "acme" / "new-repo").resolve()
    )
    assert not settings.core.workspace_dir.exists()


@pytest.mark.asyncio
async def test_toml_loads_project_board_search_query(tmp_path: Path) -> None:
    config_path = tmp_path / "dispatch.toml"
    config_path.write_text(
        '[agent]\nprompt = "Fix ${issue_number}"\n\n'
        "[watchers.issues]\n\n"
        "[[watchers.issues.repositories]]\n"
        'repo = "mariotaddeucci/bob"\n'
        'query = "project:mariotaddeucci/5"\n',
        encoding="utf-8",
    )

    settings = await load_settings(config_path)
    repository = settings.watchers.issues.repositories[0]

    assert repository.query == "project:mariotaddeucci/5"


@pytest.mark.asyncio
async def test_toml_can_configure_pull_request_watcher(tmp_path: Path) -> None:
    config_path = tmp_path / "dispatch.toml"
    config_path.write_text(
        '[agent]\nprompt = "Issue ${issue_number}"\n'
        'pull_request_prompt = "Review ${pull_request_number}"\n\n'
        "[watchers.issues]\n\n"
        '[[watchers.issues.repositories]]\nrepo = "acme/api"\nquery = "is:open"\n\n'
        "[watchers.pull_requests]\npoll_interval_seconds = 45\n\n"
        "[[watchers.pull_requests.repositories]]\n"
        'repo = "acme/api"\nquery = "is:open label:review"\n'
        'coding_agent = "opencode"\n',
        encoding="utf-8",
    )

    settings = await load_settings(config_path)

    assert settings.watchers.pull_requests is not None
    assert settings.watchers.pull_requests.poll_interval_seconds == 45
    assert settings.watchers.pull_requests.repositories[0].query == "is:open label:review"
    assert settings.agent.pull_request_prompt == "Review ${pull_request_number}"


@pytest.mark.asyncio
async def test_toml_can_configure_cron_jobs_and_resolve_repository_paths(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "gh-dispatch.toml"
    config_path.write_text(
        '[core]\nworkspace_dir = "workspaces"\nstate_db_path = "state.sqlite3"\n\n'
        '[agent]\nprompt = "Issue ${issue_number}"\n\n'
        "[watchers.issues]\n\n"
        '[[watchers.issues.repositories]]\nrepo = "acme/api"\nquery = "is:open"\n\n'
        "[watchers.cron]\npoll_interval_seconds = 2\n\n"
        "[[watchers.cron.jobs]]\n"
        'id = "weekly-maintenance"\n'
        'schedule = "0 9 * * 1"\n'
        'timezone = "Europe/Rome"\n'
        'start_date = "2026-10-05T00:00:00+02:00"\n'
        'end_date = "2026-12-31T23:59:00+01:00"\n'
        'repo = "acme/api"\n'
        'path = "checkout"\n'
        'prompt = "Maintain ${repo} at ${task_number}"\n'
        'coding_agent = "opencode"\n',
        encoding="utf-8",
    )

    settings = await load_settings(config_path)

    assert settings.watchers.cron is not None
    configured_job = settings.watchers.cron.jobs[0]
    assert configured_job.id == "weekly-maintenance"
    assert configured_job.timezone == "Europe/Rome"
    assert configured_job.path == (config_dir / "checkout").resolve()
    assert configured_job.start_date is not None
    start_offset = configured_job.start_date.utcoffset()
    assert start_offset is not None
    assert start_offset.total_seconds() == 2 * 60 * 60
    assert settings.core.state_db_path == (config_dir / "state.sqlite3").resolve()


@pytest.mark.asyncio
async def test_unknown_toml_field_is_rejected(tmp_path: Path) -> None:
    repo_path = tmp_path / "checkout"
    repo_path.mkdir()
    config_path = write_config(tmp_path / "gh-dispatch.toml", repo_path, "unexpected = true")

    with pytest.raises(ValidationError):
        await load_settings(config_path)


@pytest.mark.asyncio
async def test_duplicate_repositories_are_rejected(tmp_path: Path) -> None:
    repo_path = tmp_path / "checkout"
    repo_path.mkdir()
    config_path = write_config(tmp_path / "gh-dispatch.toml", repo_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + (
            '\n[[watchers.issues.repositories]]\nrepo = "acme/api"\n'
            'path = "checkout"\nquery = "is:open"\n'
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="repository entries must be unique"):
        await load_settings(config_path)


@pytest.mark.asyncio
async def test_missing_config_file_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="configuration file not found"):
        await load_settings(tmp_path / "absent.toml")


def test_prompt_placeholder_is_validated() -> None:
    with pytest.raises(ValidationError, match="unsupported prompt placeholder"):
        AppSettings.model_validate(
            {
                "agent": {"prompt": "${unknown}"},
                "watchers": {
                    "issues": {
                        "repositories": [
                            {
                                "repo": "acme/api",
                                "query": "is:open",
                            }
                        ]
                    }
                },
            }
        )


def test_max_active_tasks_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        AppSettings.model_validate(
            {
                "core": {"max_active_tasks": 0},
                "agent": {"prompt": "Fix ${issue_number}"},
                "watchers": {
                    "issues": {
                        "repositories": [
                            {
                                "repo": "acme/api",
                                "path": ".",
                                "query": "is:open",
                            }
                        ]
                    }
                },
            }
        )


def test_coding_agent_profiles_accept_all_cli_providers() -> None:
    settings = AppSettings.model_validate(
        {
            "agent": {"prompt": "Fix ${issue_number}"},
            "coding_agents": {
                "default": "open-code",
                "profiles": {
                    "open-code": {"provider": "opencode"},
                    "codex": {
                        "provider": "codex",
                        "model": "gpt-5.4",
                        "agent": "automation",
                        "effort": "high",
                    },
                    "claude": {
                        "provider": "claude",
                        "model": "sonnet",
                        "agent": "reviewer",
                        "effort": "high",
                    },
                    "cursor": {
                        "provider": "cursor",
                        "model": "composer-2.5",
                        "agent": "plan",
                    },
                },
            },
            "watchers": {"issues": {"repositories": [{"repo": "acme/api", "query": "is:open"}]}},
        }
    )

    assert {profile.provider for profile in settings.coding_agents.profiles.values()} == {
        "opencode",
        "codex",
        "claude",
        "cursor",
    }


def test_cursor_profile_rejects_unsupported_effort_option() -> None:
    with pytest.raises(ValidationError, match="Cursor CLI provider does not support"):
        AppSettings.model_validate(
            {
                "agent": {"prompt": "Fix ${issue_number}"},
                "coding_agents": {
                    "default": "cursor",
                    "profiles": {"cursor": {"provider": "cursor", "effort": "high"}},
                },
                "watchers": {
                    "issues": {"repositories": [{"repo": "acme/api", "query": "is:open"}]}
                },
            }
        )
