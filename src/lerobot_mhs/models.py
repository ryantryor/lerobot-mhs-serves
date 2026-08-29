"""Validation and loading for the independent MHS-compatible v0.1 profile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class ManifestError(ValueError):
    """Raised when a device profile cannot be used safely."""


REQUIRED_FIELDS = ("schema", "device", "capabilities", "observations", "commands", "safety")
VALID_MODES = {"simulation", "dry_run", "physical"}


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the safety-critical shape used by the reference runtime.

    This is an independent compatibility profile, not Anthropic's unpublished
    MHS schema. The validator intentionally rejects incomplete profiles.
    """

    missing = [field for field in REQUIRED_FIELDS if field not in manifest]
    if missing:
        raise ManifestError(f"Missing required fields: {', '.join(missing)}")
    if manifest["schema"] != "mhs-compatible/0.1":
        raise ManifestError("schema must be mhs-compatible/0.1")

    device = manifest["device"]
    if not isinstance(device, Mapping) or not device.get("id") or not device.get("kind"):
        raise ManifestError("device.id and device.kind are required")
    if not isinstance(manifest["capabilities"], list) or not manifest["capabilities"]:
        raise ManifestError("capabilities must be a non-empty list")
    if not isinstance(manifest["observations"], list):
        raise ManifestError("observations must be a list")

    commands = manifest["commands"]
    if not isinstance(commands, list):
        raise ManifestError("commands must be a list")
    command_ids: set[str] = set()
    for command in commands:
        if not isinstance(command, Mapping) or not command.get("id"):
            raise ManifestError("every command needs an id")
        command_id = str(command["id"])
        if command_id in command_ids:
            raise ManifestError(f"duplicate command id: {command_id}")
        command_ids.add(command_id)
        inputs = command.get("input", {})
        if not isinstance(inputs, Mapping):
            raise ManifestError(f"command {command_id}.input must be an object")
        for name, spec in inputs.items():
            if not isinstance(spec, Mapping):
                raise ManifestError(f"command {command_id}.{name} must be an object")
            if "type" not in spec:
                raise ManifestError(f"command {command_id}.{name}.type is required")
            if "min" in spec and "max" in spec and spec["min"] > spec["max"]:
                raise ManifestError(f"command {command_id}.{name} has inverted bounds")

    safety = manifest["safety"]
    if not isinstance(safety, Mapping):
        raise ManifestError("safety must be an object")
    default_mode = safety.get("default_mode")
    if default_mode not in VALID_MODES:
        raise ManifestError("safety.default_mode must be simulation, dry_run, or physical")
    modes = safety.get("modes", [])
    if default_mode not in modes:
        raise ManifestError("safety.modes must include safety.default_mode")
    if safety.get("emergency_stop") is not True:
        raise ManifestError("safety.emergency_stop must be explicitly declared")


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate a JSON device profile."""

    manifest_path = Path(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"Cannot load manifest {manifest_path}: {error}") from error
    if not isinstance(manifest, dict):
        raise ManifestError("manifest root must be an object")
    validate_manifest(manifest)
    return manifest
