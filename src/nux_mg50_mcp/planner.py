from __future__ import annotations

from .catalog import canonical_module
from .models import ApplyPlan, Operation, SceneSpec, ToneSpec


def _module_ops(modules, scene: int | None) -> list[Operation]:
    result: list[Operation] = []
    for raw_name, spec in modules.items():
        module = canonical_module(raw_name)
        result.append(Operation(action="click", control="module", value=module, scene=scene))
        if spec.model is not None:
            result.append(
                Operation(action="select", control=f"{module}.model", value=spec.model, scene=scene)
            )
        if spec.enabled is not None:
            result.append(
                Operation(
                    action="toggle", control=f"{module}.enabled", value=spec.enabled, scene=scene
                )
            )
        for parameter, value in spec.parameters.items():
            result.append(
                Operation(action="set", control=f"{module}.{parameter}", value=value, scene=scene)
            )
    return result


def _routing_ops(routing, scene: int | None = None) -> list[Operation]:
    result = [Operation(action="select", control="routing.mode", value=routing.mode, scene=scene)]
    if "chain" in routing.model_fields_set:
        result.append(
            Operation(action="arrange", control="routing.chain", value=routing.chain, scene=scene)
        )
    if "chain_a" in routing.model_fields_set:
        result.append(
            Operation(
                action="arrange", control="routing.chain_a", value=routing.chain_a, scene=scene
            )
        )
    if "chain_b" in routing.model_fields_set:
        result.append(
            Operation(
                action="arrange", control="routing.chain_b", value=routing.chain_b, scene=scene
            )
        )
    for field in ("split_mode", "a_level", "b_level"):
        value = getattr(routing, field)
        if value is not None:
            result.append(
                Operation(action="set", control=f"routing.{field}", value=value, scene=scene)
            )
    return result


def _scene_ops(
    number: int,
    scene: SceneSpec,
    *,
    base_routing=None,
    base_modules=None,
    include_base: bool = True,
    include_scene_routing: bool = True,
) -> list[Operation]:
    result = [Operation(action="click", control="scene", value=number, scene=number)]
    routing = (scene.routing if include_scene_routing else None) or (
        base_routing if include_base else None
    )
    if routing is not None:
        result.extend(_routing_ops(routing, number))
    if include_base and base_modules:
        result.extend(_module_ops(base_modules, number))
    result.extend(_module_ops(scene.modules, number))
    if scene.tempo_bpm is not None:
        result.append(Operation(action="set", control="tempo", value=scene.tempo_bpm, scene=number))
    for name, enabled in scene.stomp.items():
        result.append(
            Operation(
                action="toggle",
                control=f"{canonical_module(name)}.enabled",
                value=enabled,
                scene=number,
            )
        )
    return result


def plan_tone(spec: ToneSpec) -> ApplyPlan:
    operations: list[Operation] = []
    warnings: list[str] = []
    base_scene = spec.scene or 1
    has_scene_work = bool(
        spec.routing
        or spec.modules
        or spec.tempo_bpm is not None
        or spec.stomp
        or spec.scenes
        or spec.stomp_assignments is not None
    )
    if spec.preset is not None:
        operations.append(Operation(action="select", control="preset", value=spec.preset))
    if spec.scene is not None or has_scene_work:
        operations.append(
            Operation(action="click", control="scene", value=base_scene, scene=base_scene)
        )
    base_scene_spec = spec.scenes.get(base_scene)
    active_routing = (
        base_scene_spec.routing
        if base_scene_spec is not None and base_scene_spec.routing is not None
        else spec.routing
    )
    if active_routing is not None:
        operations.extend(_routing_ops(active_routing))
    operations.extend(_module_ops(spec.modules, spec.scene))
    if spec.tempo_bpm is not None:
        operations.append(
            Operation(action="set", control="tempo", value=spec.tempo_bpm, scene=spec.scene)
        )
    for name, enabled in spec.stomp.items():
        operations.append(
            Operation(
                action="toggle",
                control=f"{canonical_module(name)}.enabled",
                value=enabled,
                scene=spec.scene,
            )
        )
    for number in sorted(spec.scenes):
        operations.extend(
            _scene_ops(
                number,
                spec.scenes[number],
                base_routing=spec.routing,
                base_modules=spec.modules,
                include_base=number != base_scene,
                include_scene_routing=number != base_scene,
            )
        )
    if spec.scenes and max(spec.scenes) != base_scene:
        operations.append(
            Operation(action="click", control="scene", value=base_scene, scene=base_scene)
        )
    if spec.stomp_assignments is not None:
        for switch in ("A", "B", "C"):
            modules = getattr(spec.stomp_assignments, switch)
            if modules is not None:
                operations.append(
                    Operation(action="assign", control=f"stomp_assignments.{switch}", value=modules)
                )
    if spec.settings is not None:
        if spec.settings.output_mode is not None:
            operations.append(
                Operation(
                    action="set",
                    control="settings.output_mode.mode",
                    value=spec.settings.output_mode,
                )
            )
        for group in (
            "input_trim",
            "global_eq",
            "display",
            "brightness",
            "parameter_follow",
            "output_console",
            "midi",
            "other",
        ):
            for name, value in getattr(spec.settings, group).items():
                operations.append(
                    Operation(action="set", control=f"settings.{group}.{name}", value=value)
                )
    if spec.preset_name:
        operations.append(Operation(action="set", control="preset_name", value=spec.preset_name))
    if spec.save:
        operations.append(Operation(action="save", control="preset"))
    else:
        warnings.append("Changes are live but are not saved; set save=true to persist the preset.")
    return ApplyPlan(operations=operations, warnings=warnings)
