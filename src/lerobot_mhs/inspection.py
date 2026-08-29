"""Read-only device inspection and manifest drift reporting."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any


def inspect_device(
    manifest: Mapping[str, Any],
    backend: Any,
    *,
    json_safe: Callable[[Any], Any],
) -> dict[str, Any]:
    """Inspect a backend without opening new connections or sending actions."""

    metadata = _backend_metadata(backend, json_safe=json_safe)
    connected = bool(getattr(backend, "is_connected", False))
    calibrated = bool(getattr(backend, "is_calibrated", False))
    observation = json_safe(backend.get_observation()) if connected else None
    observation_keys = set(observation) if isinstance(observation, Mapping) else set()

    manifest_observations = {
        item["id"] for item in manifest.get("observations", []) if isinstance(item, Mapping) and item.get("id")
    }
    manifest_actions = {
        name
        for command in manifest.get("commands", [])
        if isinstance(command, Mapping)
        for name in command.get("input", {})
    }
    backend_observations = set(metadata.get("observation_features", {}))
    backend_actions = set(metadata.get("action_features", {}))
    differences: list[dict[str, Any]] = []

    _add_set_differences(
        differences,
        "missing_observation_feature",
        manifest_observations - backend_observations,
        "declared by the profile but not exposed by the backend",
    )
    _add_set_differences(
        differences,
        "unmapped_observation_feature",
        backend_observations - manifest_observations,
        "exposed by the backend but not declared by the profile",
    )
    _add_set_differences(
        differences,
        "missing_action_feature",
        manifest_actions - backend_actions,
        "required by a command but not exposed by the backend",
    )
    _add_set_differences(
        differences,
        "unmapped_action_feature",
        backend_actions - manifest_actions,
        "exposed by the backend but not mapped to a command",
    )
    if connected:
        _add_set_differences(
            differences,
            "unavailable_observation",
            manifest_observations - observation_keys,
            "declared by the profile but absent from the current observation",
        )
        _add_set_differences(
            differences,
            "undeclared_observation",
            observation_keys - manifest_observations,
            "present in the current observation but not declared by the profile",
        )

    profile = manifest.get("device", {})
    profile_type = profile.get("robot_type") if isinstance(profile, Mapping) else None
    backend_type = metadata.get("robot_type")
    if profile_type and backend_type and profile_type != backend_type:
        differences.append(
            {
                "kind": "identity_mismatch",
                "field": "robot_type",
                "profile": profile_type,
                "backend": backend_type,
                "message": "the active backend type differs from the profile",
            }
        )

    stop_available = callable(getattr(backend, "stop", None))
    return {
        "device_id": profile.get("id") if isinstance(profile, Mapping) else None,
        "read_only": True,
        "inspected_at": datetime.now(UTC).isoformat(),
        "status": "compatible" if not differences else "needs_review",
        "operational_status": (
            "ready" if connected and calibrated and stop_available else "blocked"
        ),
        "identity": metadata,
        "connection": {
            "connected": connected,
            "calibrated": calibrated,
            "stop_available": stop_available,
        },
        "profile": {
            "observation_features": sorted(manifest_observations),
            "action_features": sorted(manifest_actions),
        },
        "backend": {
            "observation_features": sorted(backend_observations),
            "action_features": sorted(backend_actions),
        },
        "current_observation": observation,
        "differences": differences,
    }


def _backend_metadata(backend: Any, *, json_safe: Callable[[Any], Any]) -> dict[str, Any]:
    describe = getattr(backend, "describe_backend", None)
    if callable(describe):
        value = describe()
        if isinstance(value, Mapping):
            return {
                "backend_type": str(value.get("backend_type", type(backend).__name__)),
                "robot_type": value.get("robot_type"),
                "robot_id": value.get("robot_id"),
                "observation_features": json_safe(_feature_map(value.get("observation_features"))),
                "action_features": json_safe(_feature_map(value.get("action_features"))),
            }

    metadata: dict[str, Any] = {
        "backend_type": type(backend).__name__,
        "robot_type": getattr(backend, "robot_type", None),
        "robot_id": getattr(backend, "id", None),
    }
    for name in ("observation_features", "action_features"):
        try:
            metadata[name] = json_safe(_feature_map(getattr(backend, name, {})))
        except Exception as error:
            metadata[name] = {}
            metadata[f"{name}_error"] = str(error)
    return metadata


def _feature_map(value: Any) -> dict[str, Any]:
    return {str(key): value[key] for key in value} if isinstance(value, Mapping) else {}


def _add_set_differences(
    differences: list[dict[str, Any]], kind: str, values: set[str], message: str
) -> None:
    for value in sorted(values):
        differences.append({"kind": kind, "field": value, "message": message})
