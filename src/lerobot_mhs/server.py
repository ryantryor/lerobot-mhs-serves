"""Optional MCP exposure for an MHS runtime."""

from __future__ import annotations

from .runtime import MhsRuntime


def create_mcp_server(runtime: MhsRuntime):
    """Create an MCP server without making MCP a runtime requirement."""

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise RuntimeError("Install the optional dependency with: pip install -e '.[mcp]'") from error

    server = FastMCP("lerobot-mhs")

    @server.tool()
    def describe_device() -> dict:
        """Return the device profile and declared capabilities."""

        return runtime.describe_device()

    @server.tool()
    def get_state() -> dict:
        """Read the latest device observation."""

        return runtime.get_state()

    @server.tool()
    def get_health() -> dict:
        """Return connection, calibration, mode, and stop availability."""

        return runtime.get_health()

    @server.tool()
    def plan_action(command_id: str, arguments: dict) -> dict:
        """Validate an action and create a short-lived plan without executing it."""

        return runtime.plan_action(command_id, arguments)

    @server.tool()
    def execute_action(plan_id: str, confirmation_token: str | None = None) -> dict:
        """Execute a previously validated plan, or simulate it outside physical mode."""

        return runtime.execute_action(plan_id, confirmation_token=confirmation_token)

    @server.tool()
    def stop() -> dict:
        """Request the backend's explicit hardware stop operation."""

        return runtime.stop()

    return server


def serve_mcp(runtime: MhsRuntime, transport: str = "stdio") -> None:
    if transport != "stdio":
        raise RuntimeError("network MCP transports are disabled until authentication is implemented")
    create_mcp_server(runtime).run(transport=transport)
