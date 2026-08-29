"""Safety-first runtime that maps MHS commands to a robot backend."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4


class SafetyError(RuntimeError):
    """Raised when a request would cross a declared safety boundary."""


class RobotBackend(Protocol):
    @property
    def is_connected(self) -> bool: ...

    @property
    def is_calibrated(self) -> bool: ...

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def calibrate(self) -> None: ...

    def get_observation(self) -> Mapping[str, Any]: ...

    def send_action(self, action: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def stop(self) -> Mapping[str, Any]: ...


def _now() -> datetime:
    return datetime.now(UTC)


class MhsRuntime:
    """Turn a manifest and backend into inspectable, bounded operations."""

    def __init__(
        self,
        manifest: Mapping[str, Any],
        backend: RobotBackend,
        *,
        mode: str | None = None,
        physical_execution_enabled: bool = False,
        physical_confirmation_token: str | None = None,
    ):
        from .models import validate_manifest

        validate_manifest(manifest)
        safety = manifest["safety"]
        selected_mode = mode or safety["default_mode"]
        if selected_mode not in safety["modes"]:
            raise SafetyError(f"mode {selected_mode!r} is not declared by the device")
        self.manifest = dict(manifest)
        self.backend = backend
        self.mode = selected_mode
        self.physical_execution_enabled = physical_execution_enabled
        self.physical_confirmation_token = physical_confirmation_token
        self._plans: dict[str, dict[str, Any]] = {}
        self._control_lock = Lock()

    def describe_device(self) -> dict[str, Any]:
        return dict(self.manifest)

    def get_state(self) -> dict[str, Any]:
        observation = _json_safe(self.backend.get_observation()) if self.backend.is_connected else None
        return {
            "device_id": self.manifest["device"]["id"],
            "mode": self.mode,
            "connected": self.backend.is_connected,
            "calibrated": self.backend.is_calibrated,
            "observation": observation,
            "timestamp": _now().isoformat(),
        }

    def get_health(self) -> dict[str, Any]:
        return {
            "device_id": self.manifest["device"]["id"],
            "mode": self.mode,
            "connected": self.backend.is_connected,
            "calibrated": self.backend.is_calibrated,
            "stop_available": self._has_stop(),
            "physical_execution_enabled": self.physical_execution_enabled,
            "physical_confirmation_configured": bool(self.physical_confirmation_token),
        }

    def plan_action(self, command_id: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        command = self._validate_action(command_id, arguments)
        plan_id = str(uuid4())
        plan = {
            "plan_id": plan_id,
            "device_id": self.manifest["device"]["id"],
            "command_id": command_id,
            "arguments": dict(arguments),
            "mode": self.mode,
            "expires_at": (_now() + timedelta(minutes=2)).isoformat(),
            "status": "planned",
        }
        self._plans[plan_id] = {**plan, "command": command}
        return plan

    def execute_action(
        self,
        plan_id: str,
        *,
        confirmation_token: str | None = None,
    ) -> dict[str, Any]:
        plan = self._plans.get(plan_id)
        if plan is None:
            raise SafetyError("unknown or expired action plan")
        if datetime.fromisoformat(plan["expires_at"]) < _now():
            self._plans.pop(plan_id, None)
            raise SafetyError("action plan expired; create a new plan")

        if self.mode != "physical":
            return {
                "plan_id": plan_id,
                "status": "simulated",
                "executed": False,
                "mode": self.mode,
                "arguments": plan["arguments"],
            }
        if not self.physical_execution_enabled:
            raise SafetyError("physical execution is disabled by the host")
        if not self.physical_confirmation_token or confirmation_token != self.physical_confirmation_token:
            raise SafetyError("physical execution requires host-provided explicit confirmation")
        if not self.backend.is_connected:
            raise SafetyError("device is not connected")
        if not self.backend.is_calibrated:
            raise SafetyError("device is not calibrated")

        with self._control_lock:
            result = self.backend.send_action(plan["arguments"])
            self._plans.pop(plan_id, None)
            return {
                "plan_id": plan_id,
                "status": "executed",
                "executed": True,
                "mode": self.mode,
                "result": _json_safe(result),
            }

    def stop(self) -> dict[str, Any]:
        if not self._has_stop():
            raise SafetyError("no hardware stop method is available")
        with self._control_lock:
            return {"status": "stopped", "result": _json_safe(self.backend.stop())}

    def _has_stop(self) -> bool:
        return callable(getattr(self.backend, "stop", None))

    def _validate_action(self, command_id: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        commands = {command["id"]: command for command in self.manifest["commands"]}
        command = commands.get(command_id)
        if command is None:
            raise SafetyError(f"unsupported command: {command_id}")
        inputs = command.get("input", {})
        unknown = set(arguments) - set(inputs)
        if unknown:
            raise SafetyError(f"unknown action fields: {', '.join(sorted(unknown))}")
        missing = set(inputs) - set(arguments)
        if missing:
            raise SafetyError(f"missing action fields: {', '.join(sorted(missing))}")
        for name, spec in inputs.items():
            value = arguments[name]
            if spec["type"] == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise SafetyError(f"{name} must be a number")
            if "min" in spec and value < spec["min"]:
                raise SafetyError(f"{name} is below the minimum boundary")
            if "max" in spec and value > spec["max"]:
                raise SafetyError(f"{name} is above the maximum boundary")
        return command


def _json_safe(value: Any) -> Any:
    """Convert common robot observations into MCP/JSON-safe values."""

    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _json_safe(tolist())
    return str(value)
