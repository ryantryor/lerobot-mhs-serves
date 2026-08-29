from pathlib import Path

import pytest

from lerobot_mhs.mock import MockRobotBackend
from lerobot_mhs.models import load_manifest
from lerobot_mhs.runtime import MhsRuntime, SafetyError
from lerobot_mhs.adapter import LeRobotAdapter


PROFILE = Path(__file__).parents[1] / "examples" / "mock_robot" / "profile.json"


def make_runtime(mode: str | None = None) -> tuple[MhsRuntime, MockRobotBackend]:
    backend = MockRobotBackend()
    return MhsRuntime(load_manifest(PROFILE), backend, mode=mode), backend


def test_manifest_and_device_state_are_inspectable():
    runtime, _ = make_runtime()
    assert runtime.describe_device()["schema"] == "mhs-compatible/0.1"
    state = runtime.get_state()
    assert state["connected"] is True
    assert state["observation"]["joint_1.position"] == 0.0


def test_plan_validates_bounds_without_executing():
    runtime, backend = make_runtime()
    plan = runtime.plan_action(
        "move_joint_targets",
        {"joint_1.position": 10, "joint_2.position": -20},
    )
    assert plan["status"] == "planned"
    assert backend.last_action is None

    with pytest.raises(SafetyError, match="above the maximum"):
        runtime.plan_action(
            "move_joint_targets",
            {"joint_1.position": 100, "joint_2.position": 0},
        )


def test_dry_run_never_calls_backend():
    runtime, backend = make_runtime()
    plan = runtime.plan_action("move_joint_targets", {"joint_1.position": 1, "joint_2.position": 2})
    result = runtime.execute_action(plan["plan_id"])
    assert result["status"] == "simulated"
    assert backend.last_action is None
    with pytest.raises(SafetyError, match="unknown or expired"):
        runtime.execute_action(plan["plan_id"])


def test_physical_mode_requires_host_enablement_and_confirmation():
    runtime, backend = make_runtime("physical")
    plan = runtime.plan_action("move_joint_targets", {"joint_1.position": 1, "joint_2.position": 2})
    with pytest.raises(SafetyError, match="disabled by the host"):
        runtime.execute_action(plan["plan_id"], confirmation_token="demo-token")

    runtime.physical_execution_enabled = True
    runtime.physical_confirmation_token = "demo-token"
    plan = runtime.plan_action("move_joint_targets", {"joint_1.position": 1, "joint_2.position": 2})
    with pytest.raises(SafetyError, match="explicit confirmation"):
        runtime.execute_action(plan["plan_id"])

    plan = runtime.plan_action("move_joint_targets", {"joint_1.position": 1, "joint_2.position": 2})
    result = runtime.execute_action(plan["plan_id"], confirmation_token="demo-token")
    assert result["executed"] is True
    assert backend.last_action == {"joint_1.position": 1, "joint_2.position": 2}


def test_physical_mode_requires_a_real_stop_method():
    runtime, backend = make_runtime("physical")
    runtime.physical_execution_enabled = True
    runtime.physical_confirmation_token = "demo-token"
    backend.stop = None
    plan = runtime.plan_action("move_joint_targets", {"joint_1.position": 1, "joint_2.position": 2})
    with pytest.raises(SafetyError, match="explicit backend stop"):
        runtime.execute_action(plan["plan_id"], confirmation_token="demo-token")


def test_non_finite_numbers_are_rejected():
    runtime, _ = make_runtime()
    with pytest.raises(SafetyError, match="finite number"):
        runtime.plan_action("move_joint_targets", {"joint_1.position": float("nan"), "joint_2.position": 0})


def test_stop_invalidates_pending_plans():
    runtime, _ = make_runtime()
    plan = runtime.plan_action("move_joint_targets", {"joint_1.position": 1, "joint_2.position": 2})
    runtime.stop()
    with pytest.raises(SafetyError, match="unknown or expired"):
        runtime.execute_action(plan["plan_id"])


def test_stop_is_explicit():
    runtime, backend = make_runtime()
    assert runtime.stop()["status"] == "stopped"
    assert backend.stop_count == 1


class FakeLeRobot:
    is_connected = True
    is_calibrated = True

    def connect(self):
        pass

    def disconnect(self):
        pass

    def calibrate(self):
        pass

    def get_observation(self):
        return {"joint_1.position": 3.0}

    def send_action(self, action):
        return action

    def stop(self):
        return {"stopped": True}


def test_lerobot_adapter_preserves_backend_contract():
    adapter = LeRobotAdapter(FakeLeRobot())
    assert adapter.is_connected is True
    assert adapter.get_observation()["joint_1.position"] == 3.0
    assert adapter.stop()["stopped"] is True


def test_inspection_reports_profile_and_backend_alignment():
    runtime, _ = make_runtime()
    result = runtime.inspect_device()
    assert result["read_only"] is True
    assert result["status"] == "compatible"
    assert result["operational_status"] == "ready"
    assert result["differences"] == []


def test_discovery_does_not_probe_hardware():
    runtime, _ = make_runtime()
    result = runtime.discover_devices()
    assert result["mode"] == "non-invasive"
    assert result["probed_hardware"] is False
    assert result["active_device"]["read_only"] is True


def test_inspection_reports_backend_drift():
    runtime, backend = make_runtime()
    backend.describe_backend = lambda: {
        "backend_type": "mock",
        "robot_type": "mock_robot",
        "robot_id": "mock-lerobot",
        "observation_features": {
            "joint_1.position": "number",
            "joint_2.position": "number",
            "temperature": "number",
        },
        "action_features": {
            "joint_1.position": "number",
            "joint_2.position": "number",
        },
    }
    result = runtime.inspect_device()
    assert result["status"] == "needs_review"
    assert any(item["kind"] == "unmapped_observation_feature" for item in result["differences"])
