"""Declarative Curupira extension application."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any, TypeVar

from .errors import RegistrationError, RpcError, SerializationError, ValidationError
from .runtime import invoke, shutdown_runtime
from .serialize import serialize_trigger_result
from .server import ExtensionServer, serve_stdio
from .signature import TriggerSpec, bind_arguments, build_trigger_spec, normalize_configuration

F = TypeVar("F", bound=Callable[..., Any])


class Curupira:
    """Extension application that registers typed trigger functions."""

    def __init__(
        self,
        *,
        name: str,
        version: str,
        agents: list[dict[str, Any]] | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.agents = agents or []
        self._triggers: dict[str, TriggerSpec] = {}
        self._agent_handlers: dict[str, Callable[[Any], Any]] = {}
        self._lifecycle: dict[str, Callable[[Any], Any]] = {}
        self._param_checks: dict[str, Callable[[dict[str, Any]], None]] = {}

    def trigger(self, func: F) -> F:
        """Register ``func`` as a trigger named ``func.__name__``.

        Use as ``@app.trigger`` with no parentheses and no arguments.
        """
        spec = build_trigger_spec(func)
        if spec.name in self._triggers:
            raise RegistrationError(f"duplicate trigger name {spec.name!r}")
        self._triggers[spec.name] = spec
        return func

    def param_check(
        self, trigger_name: str, fn: Callable[[dict[str, Any]], None]
    ) -> Callable[[dict[str, Any]], None]:
        """Register an extra argument check run during validate and poll."""
        self._param_checks[trigger_name] = fn
        return fn

    def on(self, method: str, handler: Callable[[Any], Any]) -> None:
        """Register a low-level JSON-RPC handler (agent/lifecycle methods)."""
        if method.startswith("agent/"):
            self._agent_handlers[method] = handler
        else:
            self._lifecycle[method] = handler

    def triggers(self) -> list[TriggerSpec]:
        """Return registered trigger specs in registration order."""
        return list(self._triggers.values())

    def run(self) -> None:
        """Serve the extension protocol on stdin/stdout until shutdown or EOF."""
        server = ExtensionServer(
            name=self.name,
            version=self.version,
            triggers=[
                {"trigger_type": spec.name, "prompt_fields": list(spec.prompt_fields)}
                for spec in self._triggers.values()
            ],
            agents=self.agents,
        )
        server.on("trigger/schema", self._handle_schema)
        server.on("trigger/validate", self._handle_validate)
        server.on("trigger/poll", self._handle_poll)
        server.on("trigger/onStarted", self._handle_lifecycle("trigger/onStarted"))
        server.on("trigger/onFinished", self._handle_lifecycle("trigger/onFinished"))
        for method, handler in self._agent_handlers.items():
            server.on(method, handler)
        for method, handler in self._lifecycle.items():
            if method not in {"trigger/onStarted", "trigger/onFinished"}:
                server.on(method, handler)
        try:
            serve_stdio(server)
        finally:
            shutdown_runtime()

    def print_manifest(self, manifest_template: str) -> None:
        """Print a filled manifest template to stdout (for plugins install)."""
        print(manifest_template.format(version=self.version, python=sys.executable))

    def _get_spec(self, trigger_type: str) -> TriggerSpec:
        spec = self._triggers.get(trigger_type)
        if spec is None:
            raise RpcError(-32003, f"unsupported trigger_type {trigger_type!r}")
        return spec

    def _handle_schema(self, params: Any) -> dict[str, Any]:
        trigger_type = (params or {}).get("trigger_type")
        if not isinstance(trigger_type, str):
            raise RpcError(-32602, "trigger_type is required")
        spec = self._get_spec(trigger_type)
        return {"schema": spec.schema, "prompt_fields": list(spec.prompt_fields)}

    def _handle_validate(self, params: Any) -> dict[str, Any]:
        trigger_type = (params or {}).get("trigger_type")
        configuration = dict((params or {}).get("configuration") or {})
        if not isinstance(trigger_type, str):
            raise RpcError(-32602, "trigger_type is required")
        try:
            spec = self._get_spec(trigger_type)
            kwargs = bind_arguments(spec, configuration)
            self._run_param_check(spec.name, kwargs)
            normalized = normalize_configuration(spec, configuration)
        except RpcError as exc:
            return {"ok": False, "error": str(exc)}
        except (ValidationError, RegistrationError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "configuration": normalized}

    def _run_param_check(self, trigger_name: str, kwargs: dict[str, Any]) -> None:
        check = self._param_checks.get(trigger_name)
        if check is not None:
            check(kwargs)

    def _handle_poll(self, params: Any) -> dict[str, Any]:
        trigger_type = (params or {}).get("trigger_type")
        automation = dict((params or {}).get("automation") or {})
        if not isinstance(trigger_type, str):
            raise RpcError(-32602, "trigger_type is required")
        spec = self._get_spec(trigger_type)
        try:
            kwargs = bind_arguments(spec, automation)
            self._run_param_check(spec.name, kwargs)
            result = invoke(spec.func, kwargs, is_async=spec.is_async)
            task = serialize_trigger_result(result, spec.return_annotation, trigger_name=spec.name)
        except RpcError:
            raise
        except (ValidationError, SerializationError, RegistrationError) as exc:
            raise RpcError(-32002, str(exc)) from exc
        except Exception as exc:
            raise RpcError(-32002, f"execution error: {exc}") from exc
        return {"task": task}

    def _handle_lifecycle(self, method: str) -> Callable[[Any], Any]:
        custom = self._lifecycle.get(method)

        def handler(params: Any) -> dict[str, Any]:
            if custom is not None:
                result = custom(params)
                return result if isinstance(result, dict) else {}
            return {}

        return handler
