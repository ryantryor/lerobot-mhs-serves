"""Non-invasive discovery of installed LeRobot plugin packages."""

from __future__ import annotations

import importlib.metadata


PLUGIN_PREFIXES = {
    "lerobot_robot_": "robot",
    "lerobot_camera_": "camera",
    "lerobot_teleoperator_": "teleoperator",
    "lerobot_policy_": "policy",
    "lerobot_env_": "environment",
}


def discover_lerobot_plugins() -> list[dict[str, str]]:
    """List installed plugin distributions without importing or connecting them."""

    plugins: list[dict[str, str]] = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        normalized = name.lower()
        kind = next(
            (kind for prefix, kind in PLUGIN_PREFIXES.items() if normalized.startswith(prefix)),
            None,
        )
        if kind is None:
            continue
        plugins.append(
            {
                "name": name,
                "version": distribution.version,
                "kind": kind,
                "status": "candidate",
                "side_effects": "not imported; hardware not probed",
            }
        )
    return sorted(plugins, key=lambda item: (item["kind"], item["name"]))
