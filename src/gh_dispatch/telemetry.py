"""OpenTelemetry spans for dispatched task outcomes."""

from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode

from gh_dispatch.models import ProcessResult, Task

_INSTRUMENTATION_NAME = "gh_dispatch"


class TaskTelemetry:
    """Record one span per task and optionally export it through OTLP/HTTP."""

    def __init__(
        self, endpoint: str | None = None, *, tracer_provider: TracerProvider | None = None
    ) -> None:
        self._owned_provider: TracerProvider | None = None
        if tracer_provider is not None:
            self._tracer = tracer_provider.get_tracer(_INSTRUMENTATION_NAME)
        elif endpoint is None:
            self._tracer = trace.NoOpTracerProvider().get_tracer(_INSTRUMENTATION_NAME)
        else:
            provider = TracerProvider(resource=Resource.create({"service.name": "gh-dispatch"}))
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            self._owned_provider = provider
            self._tracer = provider.get_tracer(_INSTRUMENTATION_NAME)

    @contextmanager
    def task_span(self, task: Task) -> Generator[Span, None, None]:
        """Create a task span carrying stable source and identity attributes."""
        identity = task.identity
        attributes = {
            "gh_dispatch.repo": identity.repo,
            "gh_dispatch.task.type": identity.task_type,
            "gh_dispatch.task.id": str(identity.number),
        }
        with self._tracer.start_as_current_span(
            f"gh_dispatch.task.{identity.task_type}",
            attributes=attributes,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                yield span
            except Exception as error:
                self.record_exception(span, error)
                raise

    def record_result(self, span: Span, result: ProcessResult) -> None:
        """Add the process outcome and mark non-zero exits as failed spans."""
        if result.returncode == 0:
            span.set_attribute("gh_dispatch.result", "success")
            return
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"process exited with status {result.returncode}"
        )
        self._record_failure(span, message)

    def record_exception(self, span: Span, error: Exception) -> None:
        """Record an exception event and the task's error outcome."""
        span.record_exception(error)
        self._record_failure(span, str(error) or type(error).__name__)

    def shutdown(self) -> None:
        """Flush and stop the OTLP exporter created by this instance, if any."""
        if self._owned_provider is not None:
            self._owned_provider.shutdown()
            self._owned_provider = None

    @staticmethod
    def _record_failure(span: Span, message: str) -> None:
        span.set_attribute("gh_dispatch.result", "failure")
        span.set_attribute("error.message", message)
        span.set_status(Status(StatusCode.ERROR, message))
