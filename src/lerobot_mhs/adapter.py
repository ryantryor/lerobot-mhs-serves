"""A narrow adapter around an already-created LeRobot Robot instance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .runtime import SafetyError


class LeRobotAdapter:
    """Expose a LeRobot ``Robot`` through the runtime's backend contract.

    The adapter accepts an instance instead of constructing hardware itself.
    This keeps serial/CAN/SDK configuration in the host application and makes
    the MHS layer testable with LeRobot's mock robot.
    """

    def __init__(self, robot: Any):
        required = ("connect", "disconnect", "get_observation", "send_action")
        missing = [name for name in required if not callable(getattr(robot, name, None))]
        if missing:
            raise TypeError(f"not a LeRobot-compatible Robot: missing {', '.join(missing)}")
        self.robot = robot

    @property
    def is_connected(self) -> bool:
        return bool(getattr(self.robot, "is_connected", False))

    @property
    def is_calibrated(self) -> bool:
        return bool(getattr(self.robot, "is_calibrated", True))

    def connect(self) -> None:
        self.robot.connect()

    def disconnect(self) -> None:
        self.robot.disconnect()

    def calibrate(self) -> None:
        self.robot.calibrate()

    def get_observation(self) -> Mapping[str, Any]:
        return self.robot.get_observation()

    def send_action(self, action: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.robot.send_action(dict(action))

    def describe_backend(self) -> Mapping[str, Any]:
        """Expose static LeRobot metadata without connecting to hardware."""

        return {
            "backend_type": type(self.robot).__name__,
            "robot_type": getattr(self.robot, "robot_type", getattr(self.robot, "name", None)),
            "robot_id": getattr(self.robot, "id", None),
            "observation_features": getattr(self.robot, "observation_features", {}),
            "action_features": getattr(self.robot, "action_features", {}),
        }

    def stop(self) -> Mapping[str, Any]:
        stop = getattr(self.robot, "stop", None) or getattr(self.robot, "emergency_stop", None)
        if not callable(stop):
            raise SafetyError(
                "This LeRobot backend does not expose a hardware stop method; "
                "physical execution is unavailable until one is provided."
            )
        result = stop()
        return result if isinstance(result, Mapping) else {"result": result}
