"""Forward stdlib logging records into a Textual RichLog widget."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from typing_extensions import override

if TYPE_CHECKING:
    from textual.widgets import RichLog

_LEVEL_STYLES = {
    logging.DEBUG: "dim",
    logging.INFO: "cyan",
    logging.WARNING: "yellow",
    logging.ERROR: "red",
    logging.CRITICAL: "bold red",
}

_LEVEL_LABELS = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warn",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


class TuiLogHandler(logging.Handler):
    """Emit colorized ``[HH:MM:SS] [level] message`` lines into a RichLog."""

    def __init__(self, write: Callable[[str], None]) -> None:
        super().__init__(level=logging.INFO)
        self._write = write

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Format one record and push it to the bound writer."""
        try:
            stamp = datetime.fromtimestamp(record.created, tz=UTC).strftime("%H:%M:%S")
            level = _LEVEL_LABELS.get(record.levelno, record.levelname.lower())
            style = _LEVEL_STYLES.get(record.levelno, "white")
            message = self.format(record)
            self._write(f"[{stamp}] [{style}][{level}][/] {message}")
        except Exception:  # noqa: BLE001  (logging.Handler.emit contract)
            self.handleError(record)


def attach_rich_log(log: RichLog, logger: logging.Logger | None = None) -> TuiLogHandler:
    """Install a handler that writes into ``log`` and return it for later removal."""
    target = logging.getLogger() if logger is None else logger

    def write(line: str) -> None:
        log.write(line)

    handler = TuiLogHandler(write)
    handler.setFormatter(logging.Formatter("%(message)s"))
    target.addHandler(handler)
    return handler
