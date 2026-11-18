import pytest

from nux_mg50_mcp.models import ToneSpec
from nux_mg50_mcp.planner import plan_tone


def test_known_model_parameters_are_checked_before_planning():
    spec = ToneSpec.model_validate(
        {"modules": {"AMP": {"model": "Twin Rvb", "parameters": {"gaim": 64}}}}
    )

    with pytest.raises(ValueError, match="unknown control 'gaim'"):
        plan_tone(spec)


def test_known_parameter_ranges_and_enums_are_checked():
    with pytest.raises(ValueError, match="at most 100"):
        plan_tone(
            ToneSpec.model_validate(
                {"modules": {"CMP": {"model": "Studio Comp", "parameters": {"thr": 101}}}}
            )
        )
    with pytest.raises(ValueError, match="must be one of"):
        plan_tone(
            ToneSpec.model_validate(
                {"modules": {"AMP": {"model": "Twin Rvb", "parameters": {"inputs": 3}}}}
            )
        )


def test_power_amp_and_ir_controls_from_long_report_are_valid():
    spec = ToneSpec.model_validate(
        {
            "modules": {
                "AMP": {
                    "model": "twin rvb",
                    "parameters": {"power amp": "6l6", "bias": 53, "level": 50},
                },
                "IR": {
                    "model": "ftwinrvb+jenc12k",
                    "parameters": {
                        "mode": "mono",
                        "microphone": "s57",
                        "position": "cap edge",
                        "distance": '2"',
                        "low cut": 85,
                        "high cut": 6800,
                    },
                },
            }
        }
    )

    assert plan_tone(spec).warnings == [
        "Changes are live but are not saved; set save=true to persist the preset."
    ]


def test_scene_partial_parameters_inherit_base_model_for_validation():
    spec = ToneSpec.model_validate(
        {
            "modules": {"MOD": {"model": "ST.Chorus"}},
            "scenes": {2: {"modules": {"MOD": {"parameters": {"inten.": 14}}}}},
        }
    )

    plan_tone(spec)


def test_unknown_future_model_remains_forward_compatible_with_warning():
    plan = plan_tone(
        ToneSpec.model_validate(
            {"modules": {"MOD": {"model": "Future Chorus", "parameters": {"flux": 42}}}}
        )
    )

    assert any("not in the bundled catalogue" in warning for warning in plan.warnings)
