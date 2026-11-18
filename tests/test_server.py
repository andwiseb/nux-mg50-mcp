import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from nux_mg50_mcp.driver import MockDriver
from nux_mg50_mcp.server import create_server


def test_server_exposes_valid_tool_schemas_and_accepts_tone_plan():
    async def exercise():
        server = create_server(MockDriver())
        tools = await server.list_tools()
        assert len(tools) == 12
        assert all(tool.input_schema.get("type") == "object" for tool in tools)
        result = await server.call_tool(
            "nux_plan_tone",
            {"spec": {"scene": 2, "tempo_bpm": 111}},
        )
        assert not result.is_error

    asyncio.run(exercise())


def test_generic_control_is_not_misrouted_to_other_settings():
    async def exercise():
        driver = MockDriver()
        server = create_server(driver)
        result = await server.call_tool(
            "nux_set_control",
            {"control": "AMP.gain", "value": 42},
        )
        assert not result.is_error
        assert driver.snapshot()["operations"] == [
            {
                "action": "set",
                "control": "AMP.gain",
                "value": 42.0,
                "scene": None,
            }
        ]

    asyncio.run(exercise())


def test_real_stdio_mcp_handshake_and_tool_call():
    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "nux_mg50_mcp.server"],
            env=dict(os.environ, NUX_DRIVER="mock"),
        )
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            initialized = await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool(
                "nux_plan_tone",
                {"spec": {"scene": 3, "tempo_bpm": 123}},
            )
            assert initialized.server_info.name == "nux-mg50-mcp"
            assert len(tools.tools) == 12
            assert not result.is_error

    asyncio.run(exercise())
