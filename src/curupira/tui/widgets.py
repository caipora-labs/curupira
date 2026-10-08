"""Dashboard panels for system metrics, running agents, and orchestrator logs."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, ProgressBar, RichLog, Static
from typing_extensions import override

from curupira.tui.formatting import activity_near_limit, format_memory
from curupira.tui.status import OrchestratorStatus


class MetricsPanel(Static):
    """Top panel: CPU, memory, and activity-limit progress bars."""

    DEFAULT_CSS = """
    MetricsPanel {
        height: auto;
        border: solid #c8c8c8;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    MetricsPanel .panel-title {
        text-style: bold;
        color: #f0f0f0;
        margin-bottom: 1;
    }
    MetricsPanel .metric-row {
        height: 1;
        margin-bottom: 1;
    }
    MetricsPanel .metric-label {
        width: 22;
        color: #d0d0d0;
    }
    MetricsPanel .metric-value {
        width: 18;
        color: #e8e8e8;
    }
    MetricsPanel .metric-alert {
        color: #ff5555;
        text-style: bold;
    }
    MetricsPanel #cpu-bar Bar > .bar--bar {
        color: #3ecf6a;
    }
    MetricsPanel #memory-bar Bar > .bar--bar {
        color: #4fc3f7;
    }
    MetricsPanel #activity-bar Bar > .bar--bar {
        color: #ff7043;
    }
    """

    @override
    def compose(self) -> ComposeResult:
        """Lay out labeled progress bars for host and activity metrics."""
        yield Label("MÉTRICAS DO SISTEMA", classes="panel-title")
        with Horizontal(classes="metric-row"):
            yield Label("CPU:", classes="metric-label")
            yield ProgressBar(total=100, show_eta=False, id="cpu-bar")
            yield Label("0.0%", classes="metric-value", id="cpu-value")
        with Horizontal(classes="metric-row"):
            yield Label("MEMÓRIA:", classes="metric-label")
            yield ProgressBar(total=100, show_eta=False, id="memory-bar")
            yield Label("0.0 GB / 0.0 GB", classes="metric-value", id="memory-value")
        with Horizontal(classes="metric-row"):
            yield Label("LIMITE DE ATIVIDADES:", classes="metric-label")
            yield ProgressBar(total=100, show_eta=False, id="activity-bar")
            yield Label("0 / 0 Máximo", classes="metric-value", id="activity-value")
            yield Label("", classes="metric-alert", id="activity-alert")

    def update_host(self, cpu_percent: float, used_bytes: int, total_bytes: int) -> None:
        """Refresh CPU and memory bars from host samples."""
        cpu_bar = self.query_one("#cpu-bar", ProgressBar)
        cpu_bar.update(progress=min(100.0, max(0.0, cpu_percent)))
        self.query_one("#cpu-value", Label).update(f"{cpu_percent:.1f}%")

        memory_ratio = 0.0 if total_bytes <= 0 else (used_bytes / total_bytes) * 100.0
        memory_bar = self.query_one("#memory-bar", ProgressBar)
        memory_bar.update(progress=min(100.0, max(0.0, memory_ratio)))
        self.query_one("#memory-value", Label).update(format_memory(used_bytes, total_bytes))

    def update_activity(self, active: int, limit: int) -> None:
        """Refresh the activity-limit bar and near-limit alert."""
        ratio = 0.0 if limit <= 0 else (active / limit) * 100.0
        self.query_one("#activity-bar", ProgressBar).update(progress=min(100.0, max(0.0, ratio)))
        self.query_one("#activity-value", Label).update(f"{active} / {limit} Máximo")
        alert = self.query_one("#activity-alert", Label)
        alert.update("ALERTA: PRÓXIMO AO LIMITE" if activity_near_limit(active, limit) else "")


class AgentsPanel(Static):
    """Middle panel listing active coding-agent tasks."""

    DEFAULT_CSS = """
    AgentsPanel {
        height: 1fr;
        border: solid #c8c8c8;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    AgentsPanel .panel-title {
        text-style: bold;
        color: #f0f0f0;
        margin-bottom: 1;
    }
    AgentsPanel #agents-body {
        height: 1fr;
        color: #e8e8e8;
    }
    """

    @override
    def compose(self) -> ComposeResult:
        """Create the title and a static body for agent rows."""
        yield Label("AGENTES EM EXECUÇÃO (0 de 0 ativos)", classes="panel-title", id="agents-title")
        yield Static("Nenhum agente em execução.", id="agents-body")

    def render_rows(self, status: OrchestratorStatus) -> None:
        """Replace the agent list with the current status snapshot."""
        title = self.query_one("#agents-title", Label)
        title.update(f"AGENTES EM EXECUÇÃO ({len(status.tasks)} de {status.limit} ativos)")
        body = self.query_one("#agents-body", Static)
        rows = status.rows()
        if not rows:
            body.update("Nenhum agente em execução.")
            return
        text = Text()
        for index, row in enumerate(rows):
            if index:
                text.append("\n")
            text.append("● ", style="green")
            text.append(f"{row.display_id:<8}", style="green")
            text.append(f"{row.provider:<14}")
            text.append(f"{row.elapsed:<10}", style="dim")
            text.append(row.description)
        body.update(text)


class LogsPanel(Static):
    """Bottom panel streaming orchestrator log lines."""

    DEFAULT_CSS = """
    LogsPanel {
        height: 1fr;
        border: solid #c8c8c8;
        padding: 0 1;
    }
    LogsPanel .panel-title {
        text-style: bold;
        color: #f0f0f0;
        margin-bottom: 1;
    }
    LogsPanel RichLog {
        height: 1fr;
        background: #000000;
        color: #e0e0e0;
        border: none;
        scrollbar-size-vertical: 1;
    }
    """

    @override
    def compose(self) -> ComposeResult:
        """Create the titled scrolling log widget."""
        yield Label("LOGS DO ORQUESTRADOR", classes="panel-title")
        yield RichLog(id="orchestrator-log", highlight=False, markup=True, max_lines=500)
