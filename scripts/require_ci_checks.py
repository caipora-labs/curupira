"""Fail unless required GitHub check runs succeeded for a commit."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

# Keep in sync with the job `name:` values in .github/workflows/ci.yml.
REQUIRED_CHECKS = frozenset(
    {
        "Ruff lint and format",
        "Strict type check",
        "Tests (Python 3.11)",
        "Tests (Python 3.12)",
        "Tests (Python 3.13)",
        "Tests (Python 3.14)",
        "Build and smoke-test distributions",
    }
)


def main(argv: list[str] | None = None) -> None:
    """Exit non-zero when any required check is missing or unsuccessful."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GH_REPOSITORY", ""))
    parser.add_argument("--sha", default=os.environ.get("RELEASE_SHA", ""))
    args = parser.parse_args(argv)
    if not args.repository or not args.sha:
        message = "Both --repository/--sha and GH_REPOSITORY/RELEASE_SHA are required"
        raise SystemExit(message)
    require_successful_checks(args.repository, args.sha)


def require_successful_checks(repository: str, sha: str) -> None:
    """Raise SystemExit when required CI checks are incomplete or unsuccessful."""
    url = f"https://api.github.com/repos/{repository}/commits/{sha}/check-runs?per_page=100"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        checks = json.load(response)["check_runs"]

    latest: dict[str, dict[str, object]] = {}
    for check in checks:
        name = check["name"]
        if name in REQUIRED_CHECKS and (
            name not in latest or check["started_at"] > latest[name]["started_at"]
        ):
            latest[name] = check

    missing = sorted(REQUIRED_CHECKS - latest.keys())
    failed = sorted(
        name
        for name in REQUIRED_CHECKS & latest.keys()
        if latest[name]["status"] != "completed" or latest[name]["conclusion"] != "success"
    )
    if missing or failed:
        message = f"CI validation is incomplete or unsuccessful; missing={missing}, failed={failed}"
        raise SystemExit(message)


if __name__ == "__main__":
    main()
