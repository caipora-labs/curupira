"""CLI validation, argument contracts, and user-facing failure statuses."""

from pathlib import Path

import pytest

from gh_dispatch.cli import CliOptions, _build_parser, async_main
from gh_dispatch.config import load_settings


def test_parser_supports_source_independent_commands(tmp_path: Path) -> None:
    parsed = _build_parser().parse_args(
        ["--config", str(tmp_path / "config.toml"), "run", "--dry-run"]
    )
    options = CliOptions.model_validate(vars(parsed))
    assert options.command == "run"
    assert options.dry_run
    assert _build_parser().parse_args(["watch"]).command == "watch"


async def test_validate_is_side_effect_free_for_cron_only_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[settings]\nstate_db_path="state.sqlite3"\n'
        '[coding_agents.automations.daily]\ntrigger_type="cron"\nrepo="acme/api"\n'
        'schedule="0 9 * * *"\nprompt="Maintain ${repo}"\n',
        encoding="utf-8",
    )
    assert await async_main(CliOptions(command="validate", config=path)) == 0
    assert "1 automations" in capsys.readouterr().out
    assert sorted(item.name for item in tmp_path.iterdir()) == ["config.toml"]


async def test_example_configuration_is_valid(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[1] / "gh-dispatch.example.toml"
    settings = await load_settings(example)
    assert sorted(settings.resolve_automations()) == [
        "resolve-ready-issues",
        "review-pull-requests",
        "weekly-maintenance",
    ]
    assert list(tmp_path.iterdir()) == []


async def test_configuration_error_has_actionable_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await async_main(CliOptions(command="run", config=tmp_path / "absent.toml")) == 2
    assert "configuration file not found" in capsys.readouterr().err
