from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    @model_validator(mode="after")
    def validate_layout(self) -> RoutingSpec:
        if self.mode == "serial":
            if self.chain_a or self.chain_b:
                raise ValueError("serial routing uses chain, not chain_a/chain_b")
            if len(self.chain) > 14:
                raise ValueError("serial routing supports at most 14 module slots")
        else:
            if self.chain:
                raise ValueError("split routing uses chain_a and chain_b, not chain")
            limit = 6 if self.mode == "parallel_merge" else 7
            if len(self.chain_a) > limit or len(self.chain_b) > limit:
                raise ValueError(f"{self.mode} supports at most {limit} modules per branch")
        return self


class SceneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    routing: RoutingSpec | None = None
    modules: dict[str, ModuleSpec] = Field(default_factory=dict)
    tempo_bpm: float | None = Field(default=None, ge=40, le=240)
    stomp: dict[str, bool] = Field(default_factory=dict)


class DeviceSettings(BaseModel):
    """Global/editor settings, kept data-driven for forward compatibility."""

    model_config = ConfigDict(extra="forbid")
    input_trim: dict[str, float] = Field(default_factory=dict)
    output_mode: str | None = None
    global_eq: dict[str, float | int | bool | str] = Field(default_factory=dict)
    display: dict[str, str] = Field(default_factory=dict)
    brightness: dict[str, int] = Field(default_factory=dict)
    parameter_follow: dict[str, bool] = Field(default_factory=dict)
    output_console: dict[str, float | int | bool | str] = Field(default_factory=dict)
    midi: dict[str, float | int | bool | str] = Field(default_factory=dict)
    other: dict[str, float | int | bool | str] = Field(default_factory=dict)


class ToneSpec(BaseModel):
    """A complete or partial, scene-aware MG-50Li tone request."""

    model_config = ConfigDict(extra="forbid")
    preset: str | int | None = None
    preset_name: str | None = Field(default=None, max_length=32)
    preset_volume_db: float | None = Field(default=None, ge=-12, le=12)
    scene: SceneNumber | None = None
    tempo_bpm: float | None = Field(default=None, ge=40, le=240)
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
