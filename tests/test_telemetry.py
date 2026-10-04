"""OTLP task spans and disabled-by-default behavior."""

from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import cast

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from typing_extensions import override

from gh_dispatch.executor import TaskExecutor
from gh_dispatch.models import (
    ExecutionSettings,
    ProcessResult,
    RunningCodingSession,
    Task,
    TaskIdentity,
)
from gh_dispatch.repositories import CronScheduleRepository, RunningSessionRepository
from gh_dispatch.telemetry import TaskTelemetry
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
            assert attributes["gh_dispatch.repo"] == "acme/api"
            assert attributes["gh_dispatch.task.type"] == task.identity.task_type
            assert attributes["gh_dispatch.task.id"] == str(task.identity.number)
            assert attributes["gh_dispatch.result"] == "success"
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
        assert attributes["gh_dispatch.repo"] == "acme/api"
        assert attributes["gh_dispatch.task.type"] == "issue"
        assert attributes["gh_dispatch.task.id"] == "42"
        assert attributes["gh_dispatch.result"] == "success"
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
        assert attributes["gh_dispatch.result"] == "failure"
        assert attributes["error.message"] == "agent exited unexpectedly"
        assert span.status.status_code == StatusCode.ERROR
    finally:
        provider.shutdown()


def test_task_exception_is_exported_as_failure(tmp_path: Path) -> None:
    telemetry, provider, exporter = telemetry_with_exporter()

    try:
        with (
            pytest.raises(RuntimeError, match="checkout unavailable"),
            telemetry.task_span(issue_task(tmp_path)),
        ):
            raise RuntimeError("checkout unavailable")

        [span] = exporter.get_finished_spans()
        attributes = span.attributes or {}
        assert attributes["gh_dispatch.result"] == "failure"
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


def test_configured_endpoint_receives_otlp_http_protobuf(tmp_path: Path) -> None:
    payloads: list[bytes] = []

    class CollectorHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            payloads.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), CollectorHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/traces"
    telemetry = TaskTelemetry(endpoint)
    try:
        with telemetry.task_span(issue_task(tmp_path)) as span:
            telemetry.record_result(span, ProcessResult(returncode=0))
        telemetry.shutdown()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert len(payloads) == 1
    exported = ExportTraceServiceRequest.FromString(payloads[0])
    spans = exported.resource_spans[0].scope_spans[0].spans
    assert len(spans) == 1
    attributes = {item.key: item.value.string_value for item in spans[0].attributes}
    assert attributes["gh_dispatch.repo"] == "acme/api"
    assert attributes["gh_dispatch.task.type"] == "issue"
    assert attributes["gh_dispatch.task.id"] == "42"
    assert attributes["gh_dispatch.result"] == "success"
