from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer

from .driver import Driver, MockDriver, NuxAudioDriver
from .device_catalog import capabilities
from .models import ModuleSpec, StompAssignments, ToneSpec
from .planner import plan_tone


INSTRUCTIONS = """Control the NUX MG-50Li through the local NUX Audio editor.
Prefer nux_apply_tone for complete changes: it orders preset, scene, routing, model,
switch and knob operations safely. Use dry_run first when the user's request is
ambiguous. Changes are not persisted unless save=true. Never invent a knob value;
omit parameters the user did not specify or deliberately choose them from the user's
tone description. nux_snapshot is the source of truth for the currently visible UI.
"""


def default_driver() -> Driver:
    if os.environ.get("NUX_DRIVER", "").casefold() == "mock":
        return MockDriver()
    return NuxAudioDriver()


def create_server(driver: Driver | None = None) -> MCPServer:
    active = driver or default_driver()
    server = MCPServer(
        name="nux-mg50-mcp",
        title="NUX MG-50Li Control",
        description="Scene-aware NUX MG-50Li preset, stomp, tempo, routing, module and settings control on macOS",
        instructions=INSTRUCTIONS,
        version="0.2.0",
    )

    @server.tool()
    def nux_doctor() -> dict[str, Any]:
        """Check NUX Audio, macOS Accessibility permission, and driver readiness."""
        return active.status()

    @server.tool()
    def nux_snapshot() -> dict[str, Any]:
        """Read visible NUX Audio controls and values. Use for discovery and verification."""
        return active.snapshot()

    @server.tool()
    def nux_capabilities(module: str | None = None) -> dict[str, Any]:
        """List routing, model, knob and settings metadata; optionally filter to one module."""
        return capabilities(module)

    @server.tool()
    def nux_plan_tone(spec: ToneSpec) -> dict[str, Any]:
        """Validate and show the ordered operations for a complete/partial tone without changing the device."""
        return plan_tone(spec).model_dump()

    @server.tool()
    def nux_apply_tone(spec: ToneSpec, dry_run: bool = False) -> dict[str, Any]:
        """Apply preset, S1-S3 scenes, modules/knobs, stomp, tempo, routing and global settings in one request."""
        return active.apply(plan_tone(spec), dry_run=dry_run)

    @server.tool()
    def nux_set_scene(scene: int) -> dict[str, Any]:
        """Select scene S1, S2 or S3."""
        return active.apply(plan_tone(ToneSpec(scene=scene)))

    @server.tool()
    def nux_set_preset(preset: str, save: bool = False) -> dict[str, Any]:
        """Select a preset by displayed name/slot; optionally save the live buffer."""
        return active.apply(plan_tone(ToneSpec(preset=preset, save=save)))

    @server.tool()
    def nux_set_tempo(bpm: float, scene: int | None = None) -> dict[str, Any]:
        """Set tempo in BPM (30-300), optionally in a selected scene."""
        return active.apply(plan_tone(ToneSpec(scene=scene, tempo_bpm=bpm)))

    @server.tool()
    def nux_set_stomp(block: str, enabled: bool, scene: int | None = None) -> dict[str, Any]:
        """Turn any stomp-assigned block on/off, optionally in a selected scene."""
        return active.apply(plan_tone(ToneSpec(scene=scene, stomp={block: enabled})))

    @server.tool()
    def nux_assign_stomp(
        switch: str,
        modules: list[str],
    ) -> dict[str, Any]:
        """Assign zero or more effect blocks to physical stomp switch A, B or C."""
        normalized = switch.upper()
        if normalized not in {"A", "B", "C"}:
            raise ValueError("switch must be A, B, or C")
        assignments = StompAssignments.model_validate({normalized: modules})
        return active.apply(plan_tone(ToneSpec(stomp_assignments=assignments)))

    @server.tool()
    def nux_set_module(
        module: str,
        model: str | None = None,
        enabled: bool | None = None,
        parameters: dict[str, float | int | str | bool] | None = None,
        scene: int | None = None,
    ) -> dict[str, Any]:
        """Select a model, bypass state, and arbitrary named knobs for one signal-chain module."""
        spec = ModuleSpec(model=model, enabled=enabled, parameters=parameters or {})
        return active.apply(plan_tone(ToneSpec(scene=scene, modules={module: spec})))

    @server.tool()
    def nux_set_control(control: str, value: float | int | str | bool) -> dict[str, Any]:
        """Forward-compatible escape hatch for a visible control not yet in the high-level schema."""
        spec = ToneSpec(settings={"other": {control: value}})
        return active.apply(plan_tone(spec))

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
