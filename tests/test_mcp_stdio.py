import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PROFILE = Path(__file__).parents[1] / "examples" / "mock_robot" / "profile.json"


def _tool_json(result):
    if result.structuredContent is not None:
        return result.structuredContent
    text = next(item.text for item in result.content if getattr(item, "type", None) == "text")
    return json.loads(text)


def test_mcp_stdio_round_trip():
    async def run():
        params = StdioServerParameters(
            command=str(Path(".venv/Scripts/lerobot-mhs.exe").resolve()),
            args=["serve", str(PROFILE)],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert {tool.name for tool in listed.tools} == {
                    "discover_devices",
                    "describe_device",
                    "execute_action",
                    "get_health",
                    "get_state",
                    "inspect_device",
                    "plan_action",
                    "stop",
                }

                described = _tool_json(await session.call_tool("describe_device", {}))
                assert described["schema"] == "mhs-compatible/0.1"
                inspected = _tool_json(await session.call_tool("inspect_device", {}))
                assert inspected["read_only"] is True
                assert inspected["status"] == "compatible"
                discovered = _tool_json(await session.call_tool("discover_devices", {}))
                assert discovered["probed_hardware"] is False
                planned_result = await session.call_tool(
                        "plan_action",
                        {
                            "command_id": "move_joint_targets",
                            "arguments": {"joint_1.position": 5, "joint_2.position": -3},
                        },
                )
                assert planned_result.structuredContent is not None
                planned = _tool_json(planned_result)
                simulated = _tool_json(
                    await session.call_tool("execute_action", {"plan_id": planned["plan_id"]})
                )
                assert simulated["status"] == "simulated"

    asyncio.run(run())
