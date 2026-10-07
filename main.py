"""MkDocs macros for rendering versioned documentation data."""

from pathlib import Path
import tomllib


def define_env(env):
    """Register macros used by the documentation pages."""
    requirements_path = Path(__file__).parent / "docs" / "data" / "requirements.toml"
    with requirements_path.open("rb") as requirements_file:
        requirements = tomllib.load(requirements_file)

    @env.macro
    def requirements_list():
        """Render the installation requirements from the TOML source."""
        python = requirements["python"]
        lines = [
            f"- Python {python['range']} ({python['platforms']}).",
        ]
        lines.extend(
            f"- [{tool['name']}]({tool['url']}) — {tool['detail']}"
            for tool in requirements["required_tools"]
        )
        lines.append("- Install only the CLIs used by configured profiles:")
        lines.extend(
            f"  - [{profile['name']}]({profile['url']})"
            for profile in requirements["optional_profiles"]
        )
        return "\n".join(lines)
