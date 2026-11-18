from __future__ import annotations

from typing import Any

from .catalog import canonical_module
from .device_catalog import CATALOG
from .models import ModuleSpec, ToneSpec


def _norm(value: object) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _named(mapping: dict[str, Any], wanted: str) -> tuple[str, Any] | None:
    normalized = _norm(wanted)
    return next(
        ((name, value) for name, value in mapping.items() if _norm(name) == normalized),
        None,
    )


def _validate_value(path: str, value: object, metadata: object) -> None:
    if isinstance(metadata, list):
        if not any(_norm(value) == _norm(option) for option in metadata):
            raise ValueError(f"{path} must be one of {metadata}; got {value!r}")
        return
    if not isinstance(metadata, dict):
        return
    kind = metadata.get("type")
    if kind == "boolean" and not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean; got {value!r}")
    if kind in {"number", "integer"} and (
        isinstance(value, bool) or not isinstance(value, (int, float))
    ):
        raise ValueError(f"{path} must be numeric; got {value!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = metadata.get("min")
        maximum = metadata.get("max")
        if minimum is not None and value < minimum:
            raise ValueError(f"{path} must be at least {minimum}; got {value!r}")
        if maximum is not None and value > maximum:
            raise ValueError(f"{path} must be at most {maximum}; got {value!r}")


def _module_metadata(module: str, model: str) -> tuple[str, dict[str, Any]] | None:
    canonical = canonical_module(module)
    section_name = "AMP" if canonical == "AMP2" else canonical
    section = CATALOG.get(section_name)
    if section is None:
        return None
    if canonical == "IR":
        match = next(
            (slot for slot in section["slots"] if slot is not None and _norm(slot) == _norm(model)),
            None,
        )
        return (match, {}) if match is not None else None
    models = section.get("models", {})
    found = _named(models, model)
    if found is None and canonical in {"AMP", "AMP2"}:
        found = _named(CATALOG["AMP_IMAGE"]["models"], model)
    return found


def _extra_parameters(module: str) -> dict[str, object]:
    canonical = canonical_module(module)
    if canonical in {"AMP", "AMP2"}:
        power_models = CATALOG["POWER_AMP"]["models"]
        combined: dict[str, object] = {"power amp": list(power_models)}
        for parameters in power_models.values():
            combined.update(parameters)
        return combined
    if canonical == "IR":
        ir = CATALOG["IR"]
        return {
            "mode": ir["modes"],
            "microphone": ir["microphones"],
            "mic": ir["microphones"],
            "position": ir["positions"],
            "distance": ir["distances"],
            "level": {},
            "level_db": {},
            "low cut": {},
            "low_cut_hz": {},
            "high cut": {},
            "high_cut_hz": {},
            "pan": {},
        }
    return {}


def _validate_module(
    path: str, module: str, spec: ModuleSpec, inherited: ModuleSpec | None
) -> list[str]:
    warnings: list[str] = []
    model = spec.model or (inherited.model if inherited is not None else None)
    if model is None:
        return warnings
    found = _module_metadata(module, model)
    if found is None:
        warnings.append(
            f"{path}.model {model!r} is not in the bundled catalogue; "
            "it will be resolved against the live editor."
        )
        return warnings
    canonical_model, parameters = found
    allowed = dict(parameters)
    allowed.update(_extra_parameters(module))
    for raw_name, value in spec.parameters.items():
        match = _named(allowed, raw_name)
        if match is None:
            choices = ", ".join(sorted(allowed)) or "none"
            raise ValueError(
                f"{path}.parameters contains unknown control {raw_name!r} for "
                f"{canonical_model!r}; known controls: {choices}"
            )
        canonical_parameter, metadata = match
        _validate_value(f"{path}.parameters.{canonical_parameter}", value, metadata)
    return warnings


def validate_tone_spec(spec: ToneSpec) -> list[str]:
    """Fail before UI mutation for invalid controls on known bundled models.

    Unknown models/modules remain forward compatible and produce warnings because a
    newer NUX Audio release may legitimately expose them.
    """

    warnings: list[str] = []
    for module, module_spec in spec.modules.items():
        warnings.extend(_validate_module(f"modules.{module}", module, module_spec, None))
    for scene_number, scene in spec.scenes.items():
        for module, module_spec in scene.modules.items():
            inherited = spec.modules.get(module)
            if inherited is None:
                canonical = canonical_module(module)
                inherited = next(
                    (
                        candidate
                        for base_name, candidate in spec.modules.items()
                        if canonical_module(base_name) == canonical
                    ),
                    None,
                )
            warnings.extend(
                _validate_module(
                    f"scenes.{scene_number}.modules.{module}",
                    module,
                    module_spec,
                    inherited,
                )
            )
    return warnings
