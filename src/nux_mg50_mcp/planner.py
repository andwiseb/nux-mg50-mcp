from __future__ import annotations

from .catalog import canonical_module
from .models import ApplyPlan, Operation, SceneSpec, ToneSpec


def _module_ops(modules, scene: int | None) -> list[Operation]:
    result: list[Operation] = []
    for raw_name, spec in modules.items():
        module = canonical_module(raw_name)
        result.append(Operation(action="click", control="module", value=module, scene=scene))
        if spec.model is not None:
            result.append(Operation(action="select", control=f"{module}.model", value=spec.model, scene=scene))
        if spec.enabled is not None:
            result.append(Operation(action="toggle", control=f"{module}.enabled", value=spec.enabled, scene=scene))
        for parameter, value in spec.parameters.items():
            result.append(Operation(action="set", control=f"{module}.{parameter}", value=value, scene=scene))
    return result


def _scene_ops(number: int, scene: SceneSpec) -> list[Operation]:
    result = [Operation(action="click", control="scene", value=number, scene=number)]
    result.extend(_module_ops(scene.modules, number))
    if scene.tempo_bpm is not None:
        result.append(Operation(action="set", control="tempo", value=scene.tempo_bpm, scene=number))
    for name, enabled in scene.stomp.items():
        result.append(Operation(action="toggle", control=f"stomp.{name}", value=enabled, scene=number))
    return result


def plan_tone(spec: ToneSpec) -> ApplyPlan:
    operations: list[Operation] = []
    warnings: list[str] = []
    if spec.preset is not None:
        operations.append(Operation(action="select", control="preset", value=spec.preset))
    if spec.scene is not None:
        operations.append(Operation(action="click", control="scene", value=spec.scene, scene=spec.scene))
    operations.extend(_module_ops(spec.modules, spec.scene))
    if spec.tempo_bpm is not None:
        operations.append(Operation(action="set", control="tempo", value=spec.tempo_bpm, scene=spec.scene))
    for name, enabled in spec.stomp.items():
        operations.append(Operation(action="toggle", control=f"stomp.{name}", value=enabled, scene=spec.scene))
    if spec.stomp_assignments is not None:
        for switch in ("A", "B", "C"):
            modules = getattr(spec.stomp_assignments, switch)
            if modules is not None:
                operations.append(Operation(action="assign", control=f"stomp_assignments.{switch}", value=modules))
    if spec.routing is not None:
        operations.append(Operation(action="select", control="routing.mode", value=spec.routing.mode))
        if spec.routing.chain:
            operations.append(Operation(action="arrange", control="routing.chain", value=spec.routing.chain))
        if spec.routing.chain_a:
            operations.append(Operation(action="arrange", control="routing.chain_a", value=spec.routing.chain_a))
        if spec.routing.chain_b:
            operations.append(Operation(action="arrange", control="routing.chain_b", value=spec.routing.chain_b))
        for field in ("split_mode", "a_level", "b_level"):
            value = getattr(spec.routing, field)
            if value is not None:
                operations.append(Operation(action="set", control=f"routing.{field}", value=value))
    if spec.settings is not None:
        for group in ("input_trim", "global_eq", "output_console", "midi", "other"):
            for name, value in getattr(spec.settings, group).items():
                operations.append(Operation(action="set", control=f"settings.{group}.{name}", value=value))
    for number in sorted(spec.scenes):
        operations.extend(_scene_ops(number, spec.scenes[number]))
    if spec.preset_name:
        operations.append(Operation(action="set", control="preset_name", value=spec.preset_name))
    if spec.save:
        operations.append(Operation(action="save", control="preset"))
    else:
        warnings.append("Changes are live but are not saved; set save=true to persist the preset.")
    return ApplyPlan(operations=operations, warnings=warnings)
