# LeRobot MHS Serves

An independent, simulator-first **MHS-compatible** runtime for exposing LeRobot hardware to AI agents.

> This is not Anthropic's official MHS implementation. The public MHS specification is still a research-preview effort. This repository defines a deliberately small compatibility profile so we can build, test, and migrate safely when the official specification is released.

## What this does

The runtime places a safety and description layer around a LeRobot-compatible `Robot`:

- `describe_device` exposes the device identity, capabilities, observations, commands, and safety boundaries;
- `get_state` returns current observations with connection and calibration state;
- `plan_action` validates an action and creates a short-lived plan without touching hardware;
- `execute_action` simulates outside physical mode and requires host enablement plus a host-provided confirmation token in physical mode;
- `stop` requires the backend to expose a real stop or emergency-stop method;
- the optional MCP layer exposes these operations as agent tools.

The reference server is stdio-only. Network transports are intentionally disabled until authentication, authorization, rate limiting, and a controller lease are implemented.

The design follows the public direction described in Anthropic's [Model Hardware Standard research preview](https://www.anthropic.com/news/model-hardware-standard-research-preview), while keeping the implementation independent and explicit about what is not official.

## Run the mock server

Python 3.12+ is required.

```bash
uv venv
uv pip install -e ".[mcp,dev]"
lerobot-mhs validate examples/mock_robot/profile.json
lerobot-mhs describe examples/mock_robot/profile.json
lerobot-mhs serve examples/mock_robot/profile.json
```

The mock server starts in `dry_run` by default. No command from an agent can move real hardware in this example.

## Use with LeRobot

The adapter wraps an already-created LeRobot `Robot` instance. It does not guess serial ports, CAN settings, calibration files, or an emergency-stop behavior.

```python
from lerobot.robots import RobotConfig, make_robot_from_config

from lerobot_mhs import LeRobotAdapter, MhsRuntime
from lerobot_mhs.models import load_manifest

robot = make_robot_from_config(robot_config)
runtime = MhsRuntime(
    load_manifest("profile.json"),
    LeRobotAdapter(robot),
    mode="dry_run",
    # Inject this only from a trusted host, never from an agent request.
    physical_confirmation_token=None,
)
```

For real hardware, the host must provide a backend-specific `stop()` or `emergency_stop()` method. Disconnecting a robot is not treated as an emergency stop.

## Profile status

`mhs-compatible/0.1` is our independent profile, not an official Anthropic schema. It currently covers:

- device identity and runtime;
- capabilities, observations, and typed bounded commands;
- simulation, dry-run, and physical modes;
- calibration and connection requirements;
- explicit stop availability;
- telemetry declaration.

The profile is intentionally separate from the resource directory schema in [awesome-mhs-servers](https://github.com/ryantryor/awesome-mhs-servers). The directory describes projects; this profile describes how a device can be inspected and operated.

## Safety position

This project is designed to make unsafe defaults difficult, not to certify any hardware. Start with simulation, then dry-run, then supervised physical execution. Review every driver, limit, unit, watchdog, and stop path before connecting a device.

## Development

```bash
pytest
```

The next milestones are a LeRobot mock integration, a simulator-backed SO-101 profile, conformance tests for third-party adapters, and a versioned mapping to the official MHS schema when it becomes public.
