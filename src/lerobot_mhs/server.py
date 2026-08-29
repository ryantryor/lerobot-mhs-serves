"""Optional MCP exposure for an MHS runtime."""

from __future__ import annotations

from typing import Any

from .runtime import MhsRuntime


def create_mcp_server(runtime: MhsRuntime):
    """Create an MCP server without making MCP a runtime requirement."""

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise RuntimeError("Install the optional dependency with: pip install -e '.[mcp]'") from error

    server = FastMCP("lerobot-mhs")

    @server.tool(structured_output=True)
    def describe_device() -> dict[str, Any]:
        """Return the device profile and declared capabilities."""

        return runtime.describe_device()

    @server.tool(structured_output=True)
    def get_state() -> dict[str, Any]:
        """Read the latest device observation."""

        return runtime.get_state()

    @server.tool(structured_output=True)
    def get_health() -> dict[str, Any]:
        """Return connection, calibration, mode, and stop availability."""

        return runtime.get_health()

    @server.tool(structured_output=True)
    def inspect_device() -> dict[str, Any]:
        """Read-only inspection of identity, features, state, health, and profile drift."""

        return runtime.inspect_device()

    @server.tool(structured_output=True)
    def discover_devices() -> dict[str, Any]:
        """Discover the active device and installed LeRobot plugin candidates without probing hardware."""

        return runtime.discover_devices()

    @server.tool(structured_output=True)
    def plan_action(command_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate an action and create a short-lived plan without executing it."""

        return runtime.plan_action(command_id, arguments)

    @server.tool(structured_output=True)
    def execute_action(plan_id: str, confirmation_token: str | None = None) -> dict[str, Any]:
        """Execute a previously validated plan, or simulate it outside physical mode."""

        return runtime.execute_action(plan_id, confirmation_token=confirmation_token)

    @server.tool(structured_output=True)
    def stop() -> dict[str, Any]:
        """Request the backend's explicit hardware stop operation."""

        return runtime.stop()

    return server


def serve_mcp(runtime: MhsRuntime, transport: str = "stdio") -> None:
    if transport != "stdio":
        raise RuntimeError("network MCP transports are disabled until authentication is implemented")
    create_mcp_server(runtime).run(transport=transport)
