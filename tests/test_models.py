import pytest
from pydantic import ValidationError

from nux_mg50_mcp.models import ToneSpec


def test_rejects_invalid_scene_and_tempo():
    with pytest.raises(ValidationError):
        ToneSpec(scene=4, tempo_bpm=301)
    with pytest.raises(ValidationError):
        ToneSpec(tempo_bpm=39)
    with pytest.raises(ValidationError):
        ToneSpec(tempo_bpm=241)


def test_accepts_complete_surface():
    spec = ToneSpec.model_validate(
        {
            "routing": {"mode": "serial", "chain": ["NG", "AMP", "IR"]},
            "modules": {"amp": {"model": "Brit 800", "parameters": {"gain": 62}}},
            "settings": {"midi": {"channel": 1}, "other": {"patch_tail": True}},
        }
    )
    assert spec.modules["amp"].parameters["gain"] == 62


def test_accepts_full_settings_surface():
    spec = ToneSpec.model_validate(
        {
            "settings": {
                "output_mode": "Studio Direct(Line/Phones)",
                "display": {"home_display": "graphical", "boot_up_picture": "factory"},
                "brightness": {"display": 50, "footswitch": 0},
                "parameter_follow": {"enabled": False, "default_ir": True},
            }
        }
    )
    assert spec.settings is not None
    assert spec.settings.output_mode == "Studio Direct(Line/Phones)"
    assert spec.settings.brightness["display"] == 50


def test_routing_enforces_real_editor_slot_limits():
    with pytest.raises(ValidationError):
        ToneSpec.model_validate({"routing": {"mode": "parallel_merge", "chain_a": ["EFX"] * 7}})
    with pytest.raises(ValidationError):
        ToneSpec.model_validate({"routing": {"mode": "serial", "chain_a": ["AMP"]}})


def test_scene_accepts_its_own_routing_layout():
    spec = ToneSpec.model_validate(
        {
            "scenes": {
                2: {"routing": {"mode": "split_outputs", "chain_a": ["AMP"], "chain_b": ["IR"]}}
            }
        }
    )
    assert spec.scenes[2].routing is not None
    assert spec.scenes[2].routing.mode == "split_outputs"
