from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SceneNumber = Literal[1, 2, 3]


class ModuleSpec(BaseModel):
    """One block in the signal chain.

    Parameter names deliberately remain data-driven: NUX adds models and parameters in
    firmware releases, so the MCP server must not reject a new knob merely because its
    catalogue predates the firmware.
    """

    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    model: str | None = None
    parameters: dict[str, float | int | str | bool] = Field(default_factory=dict)


class SceneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modules: dict[str, ModuleSpec] = Field(default_factory=dict)
    tempo_bpm: float | None = Field(default=None, ge=30, le=300)
    stomp: dict[str, bool] = Field(default_factory=dict)


class StompAssignments(BaseModel):
    """Module assignments for the physical A/B/C stomp switches.

    A switch may control more than one block.  An empty list explicitly unassigns
    that switch; omitted switches are left untouched.
    """

    model_config = ConfigDict(extra="forbid")
    A: list[str] | None = None
    B: list[str] | None = None
    C: list[str] | None = None


class RoutingSpec(BaseModel):
    """MG-50Li signal-chain layout and split/merge configuration."""

    model_config = ConfigDict(extra="forbid")
    mode: Literal["serial", "parallel_merge", "split_outputs"] = "serial"
    chain: list[str] = Field(default_factory=list)
    chain_a: list[str] = Field(default_factory=list)
    chain_b: list[str] = Field(default_factory=list)
    split_mode: Literal["dual", "chain_a_b"] | None = None
    a_level: int | None = Field(default=None, ge=0, le=100)
    b_level: int | None = Field(default=None, ge=0, le=100)


class DeviceSettings(BaseModel):
    """Global/editor settings, kept data-driven for forward compatibility."""

    model_config = ConfigDict(extra="forbid")
    input_trim: dict[str, float] = Field(default_factory=dict)
    global_eq: dict[str, float | int | bool | str] = Field(default_factory=dict)
    output_console: dict[str, float | int | bool | str] = Field(default_factory=dict)
    midi: dict[str, float | int | bool | str] = Field(default_factory=dict)
    other: dict[str, float | int | bool | str] = Field(default_factory=dict)


class ToneSpec(BaseModel):
    """A complete or partial, scene-aware MG-50Li tone request."""

    model_config = ConfigDict(extra="forbid")
    preset: str | int | None = None
    preset_name: str | None = Field(default=None, max_length=32)
    scene: SceneNumber | None = None
    tempo_bpm: float | None = Field(default=None, ge=30, le=300)
    modules: dict[str, ModuleSpec] = Field(default_factory=dict)
    scenes: dict[int, SceneSpec] = Field(default_factory=dict)
    stomp: dict[str, bool] = Field(default_factory=dict)
    stomp_assignments: StompAssignments | None = None
    routing: RoutingSpec | None = None
    settings: DeviceSettings | None = None
    save: bool = False

    @field_validator("scenes")
    @classmethod
    def validate_scenes(cls, value: dict[int, SceneSpec]) -> dict[int, SceneSpec]:
        invalid = sorted(set(value) - {1, 2, 3})
        if invalid:
            raise ValueError(f"scene numbers must be 1, 2, or 3; got {invalid}")
        return value


class Operation(BaseModel):
    action: Literal["click", "set", "select", "toggle", "assign", "arrange", "save"]
    control: str
    value: Any = None
    scene: int | None = None


class ApplyPlan(BaseModel):
    operations: list[Operation]
    warnings: list[str] = Field(default_factory=list)
