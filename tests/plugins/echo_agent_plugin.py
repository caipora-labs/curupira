"""An installable-style coding-agent plugin that imports only the public plugin API."""

from typing import Literal

from typing_extensions import override

from curupira.models import CursorCliProfile
from curupira.plugins import CliProfileBase, CodingAgentCliAdapter, CodingTaskRequest


class EchoCliProfile(CliProfileBase):
    """Options for a fake CLI that echoes the task message.

    Attributes:
        provider: Discriminator identifying the echo CLI.
        volume: How loudly the message is echoed.
    """

    provider: Literal["echo"] = "echo"
    volume: Literal["quiet", "loud"] = "quiet"


class EchoCliAdapter(CodingAgentCliAdapter):
    """Translate echo profiles into native arguments."""

    executable = "echo-agent"
    provider = "echo"
    profile_model = EchoCliProfile
    display_name = "Echo Agent"
    install_url = "https://echo.example/"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        profile = request.profile
        if not isinstance(profile, EchoCliProfile):
            raise ValueError("echo requires an echo profile")
        return ("--volume", profile.volume, "--", request.message)


class FutureEchoCliAdapter(EchoCliAdapter):
    """An adapter written against an unsupported plugin API."""

    api_version = 3


class DuplicateCursorCliAdapter(EchoCliAdapter):
    """An adapter that tries to replace the built-in Cursor provider."""

    provider = "cursor"
    profile_model = CursorCliProfile


class MismatchedCliAdapter(EchoCliAdapter):
    """An adapter whose profile model defaults to another provider."""

    provider = "mismatch"


echo_adapter = EchoCliAdapter()
NOT_AN_ADAPTER = 42
