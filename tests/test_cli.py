from __future__ import annotations

from pathlib import Path

import pytest

from gh_dispatch.cli import CliOptions, _build_parser, async_main


def test_parser_builds_typed_validate_options(tmp_path: Path) -> None:
    namespace = _build_parser().parse_args(
        ["--config", str(tmp_path / "dispatch.toml"), "validate"]
    )

    options = CliOptions.model_validate(vars(namespace))

    assert options.command == "validate"
    assert options.config == tmp_path / "dispatch.toml"
    assert options.dry_run is False


def test_parser_accepts_watch_command(tmp_path: Path) -> None:
    namespace = _build_parser().parse_args(["--config", str(tmp_path / "dispatch.toml"), "watch"])

    options = CliOptions.model_validate(vars(namespace))

    assert options.command == "watch"


@pytest.mark.asyncio
async def test_validate_command_loads_config_without_calling_external_clis(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_path = tmp_path / "checkout"
    repo_path.mkdir()
    config_path = tmp_path / "dispatch.toml"
    config_path.write_text(
        '[agent]\nprompt = "Fix ${issue_number}"\n\n'
        "[watchers.issues]\npoll_interval_seconds = 30\n\n"
        '[[watchers.issues.repositories]]\nrepo = "acme/api"\n'
        'path = "checkout"\nquery = "is:open"\n',
        encoding="utf-8",
    )

    exit_code = await async_main(CliOptions(command="validate", config=config_path))

    assert exit_code == 0
    assert "Configuration is valid (1 watcher repositories; max active tasks: 1)." in (
        capsys.readouterr().out
    )


@pytest.mark.asyncio
async def test_validate_command_counts_cron_jobs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "dispatch.toml"
    config_path.write_text(
        '[agent]\nprompt = "Issue ${issue_number}"\n\n'
        "[watchers.issues]\n\n"
        '[[watchers.issues.repositories]]\nrepo = "acme/api"\nquery = "is:open"\n\n'
        "[watchers.cron]\n\n"
        "[[watchers.cron.jobs]]\n"
        'id = "daily"\nschedule = "0 9 * * *"\nrepo = "acme/api"\n'
        'prompt = "Maintain ${repo}"\n',
        encoding="utf-8",
    )

    exit_code = await async_main(CliOptions(command="validate", config=config_path))

    assert exit_code == 0
    assert "1 watcher repositories; 1 cron job; max active tasks: 1" in capsys.readouterr().out
