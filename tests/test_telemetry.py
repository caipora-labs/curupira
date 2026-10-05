"""OTLP task spans and disabled-by-default behavior."""

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from opscli.executor import TaskExecutor
from opscli.models import (
    ExecutionSettings,
    ProcessResult,
    RunningCodingSession,
    Task,
    TaskIdentity,
)
from opscli.repositories import CronScheduleRepository, RunningSessionRepository
from opscli.telemetry import TaskTelemetry
from tests.fakes import FakeGitHub, RecordingAdapter
from tests.helpers import issue_task, pull_request_task, resolved_automation


def cron_task(path: Path) -> Task:
    """Build a cron occurrence for telemetry identity coverage."""
    scheduled_for = datetime(2026, 10, 4, 9, tzinfo=UTC)
    return Task(
        identity=TaskIdentity(
            automation_id="maintenance",
            repo="acme/api",
            task_type="cron",
            number=int(scheduled_for.timestamp()),
        ),
        automation=resolved_automation(path, "maintenance", "cron"),
        title="Scheduled maintenance",
        url="",
        scheduled_for=scheduled_for,
    )


def telemetry_with_exporter() -> tuple[TaskTelemetry, TracerProvider, InMemorySpanExporter]:
    """Create an in-memory SDK pipeline without an external collector."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return TaskTelemetry(tracer_provider=provider), provider, exporter


class MemorySessionRepository:
    """Avoid filesystem state in the telemetry/executor integration test."""

    async def save(self, _session: RunningCodingSession) -> None:
        return

    async def delete(self, _task: Task) -> None:
        return


def test_task_spans_export_success_for_issues_pull_requests_and_cron(tmp_path: Path) -> None:
    telemetry, provider, exporter = telemetry_with_exporter()
    tasks = [issue_task(tmp_path), pull_request_task(tmp_path), cron_task(tmp_path)]

    try:
        for task in tasks:
            with telemetry.task_span(task) as span:
                telemetry.record_result(span, ProcessResult(returncode=0))

        spans = exporter.get_finished_spans()
        assert len(spans) == 3
        for span, task in zip(spans, tasks, strict=True):
            attributes = span.attributes or {}
            assert attributes["opscli.repo"] == "acme/api"
            assert attributes["opscli.task.type"] == task.identity.task_type
            assert attributes["opscli.task.id"] == str(task.identity.number)
            assert attributes["opscli.result"] == "success"
            assert span.status.status_code == StatusCode.UNSET
    finally:
        provider.shutdown()


async def test_executor_exports_the_real_task_outcome(tmp_path: Path) -> None:
    telemetry, provider, exporter = telemetry_with_exporter()
    database = tmp_path / "state.sqlite3"
    executor = TaskExecutor(
        ExecutionSettings(state_db_path=database),
        FakeGitHub(),
        cast(RunningSessionRepository, MemorySessionRepository()),
        CronScheduleRepository(database),
        adapter_factory=lambda _: RecordingAdapter(),
        telemetry=telemetry,
    )

    try:
        result = await executor.execute(issue_task(tmp_path))

        assert result.returncode == 0
        [span] = exporter.get_finished_spans()
        attributes = span.attributes or {}
        assert attributes["opscli.repo"] == "acme/api"
        assert attributes["opscli.task.type"] == "issue"
        assert attributes["opscli.task.id"] == "42"
        assert attributes["opscli.result"] == "success"
    finally:
        provider.shutdown()


def test_failed_process_span_contains_error_and_error_status(tmp_path: Path) -> None:
    telemetry, provider, exporter = telemetry_with_exporter()

    try:
        with telemetry.task_span(issue_task(tmp_path)) as span:
            telemetry.record_result(
                span, ProcessResult(returncode=2, stderr="agent exited unexpectedly")
            )

        [span] = exporter.get_finished_spans()
        attributes = span.attributes or {}
        assert attributes["opscli.result"] == "failure"
        assert attributes["error.message"] == "agent exited unexpectedly"
        assert span.status.status_code == StatusCode.ERROR
    finally:
        provider.shutdown()


def test_task_exception_is_exported_as_failure(tmp_path: Path) -> None:
    telemetry, provider, exporter = telemetry_with_exporter()

    try:
        with telemetry.task_span(issue_task(tmp_path)) as span:
            telemetry.record_exception(span, RuntimeError("checkout unavailable"))

        [span] = exporter.get_finished_spans()
        attributes = span.attributes or {}
        assert attributes["opscli.result"] == "failure"
        assert attributes["error.message"] == "checkout unavailable"
        assert span.status.status_code == StatusCode.ERROR
        assert any(event.name == "exception" for event in span.events)
    finally:
        provider.shutdown()


def test_telemetry_without_endpoint_uses_non_recording_spans(tmp_path: Path) -> None:
    telemetry = TaskTelemetry()

    with telemetry.task_span(issue_task(tmp_path)) as span:
        telemetry.record_result(span, ProcessResult(returncode=0))

    assert not span.is_recording()


def test_configured_endpoint_is_given_to_otlp_exporter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exporter = InMemorySpanExporter()
    endpoints: list[str] = []

    def create_exporter(*, endpoint: str) -> InMemorySpanExporter:
        endpoints.append(endpoint)
        return exporter

    monkeypatch.setattr("opscli.telemetry.OTLPSpanExporter", create_exporter)
    endpoint = "http://collector:4318/v1/traces"
    telemetry = TaskTelemetry(endpoint)
    try:
        with telemetry.task_span(issue_task(tmp_path)) as span:
            telemetry.record_result(span, ProcessResult(returncode=0))
    finally:
        telemetry.shutdown()

    assert endpoints == [endpoint]
    [span] = exporter.get_finished_spans()
    attributes = span.attributes or {}
    assert attributes["opscli.repo"] == "acme/api"
    assert attributes["opscli.task.type"] == "issue"
    assert attributes["opscli.task.id"] == "42"
    assert attributes["opscli.result"] == "success"
