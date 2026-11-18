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
        assert len(tools) == 13
        assert all(tool.input_schema.get("type") == "object" for tool in tools)
        apply_tool = next(tool for tool in tools if tool.name == "nux_apply_tone")
        spec_schema = apply_tool.input_schema["properties"]["spec"]
        spec_properties = spec_schema.get("properties", {})
        if not spec_properties and "$ref" in spec_schema:
            definition = spec_schema["$ref"].rsplit("/", 1)[-1]
            spec_properties = apply_tool.input_schema["$defs"][definition]["properties"]
        assert "preset_volume_db" in spec_properties
        result = await server.call_tool(
            "nux_plan_tone",
            {"spec": {"scene": 2, "tempo_bpm": 111}},
        )
        assert not result.is_error

    asyncio.run(exercise())


def test_server_advertises_language_neutral_long_document_handling():
    server = create_server(MockDriver())

    assert "multilingual tone document" in server.instructions
    assert "alternate instruments" in server.instructions
    assert "Never infer a destination preset slot" in server.instructions
    assert "call nux_apply_text" in server.instructions


def test_apply_text_uses_outer_save_flag_and_returns_source_receipt():
    async def exercise():
        driver = MockDriver()
        server = create_server(driver)
        source = "Tempo 134. Preset adı BEGGIN 17. Uygula ve kaydet."
        result = await server.call_tool(
            "nux_apply_text",
            {
                "source_text": source,
                "spec": {"preset_name": "BEGGIN 17", "tempo_bpm": 134, "save": False},
                "save": True,
            },
        )

        assert not result.is_error
        payload = result.structured_content
        assert payload["save_requested"] is True
        assert payload["source"]["characters"] == len(source)
        assert len(payload["source"]["sha256"]) == 64
        assert driver.operations[-1]["action"] == "save"

    asyncio.run(exercise())


def test_apply_text_never_trusts_embedded_spec_save_without_outer_permission():
    async def exercise():
        driver = MockDriver()
        server = create_server(driver)
        result = await server.call_tool(
            "nux_apply_text",
            {
                "source_text": "Save it",
                "spec": {"tempo_bpm": 120, "save": True},
            },
        )

        assert not result.is_error
        assert all(operation["action"] != "save" for operation in driver.operations)

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
            assert len(tools.tools) == 13
            assert not result.is_error

    asyncio.run(exercise())
