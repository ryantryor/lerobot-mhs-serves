"""Deterministic backend for tests and simulator-first development."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class MockRobotBackend:
    def __init__(self) -> None:
        self.connected = True
        self.calibrated = True
        self.last_action: dict[str, Any] | None = None
        self.stop_count = 0

    @property
    def is_connected(self) -> bool:
        return self.connected

    @property
    def is_calibrated(self) -> bool:
        return self.calibrated

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def calibrate(self) -> None:
        self.calibrated = True

    def get_observation(self) -> Mapping[str, Any]:
        return {"joint_1.position": 0.0, "joint_2.position": 0.0}

    def send_action(self, action: Mapping[str, Any]) -> Mapping[str, Any]:
        self.last_action = dict(action)
        return dict(action)

    def stop(self) -> Mapping[str, Any]:
        self.stop_count += 1
        return {"stop_count": self.stop_count}
