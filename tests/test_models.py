import pytest
from pydantic import ValidationError

from nux_mg50_mcp.models import ToneSpec


def test_rejects_invalid_scene_and_tempo():
    with pytest.raises(ValidationError):
        ToneSpec(scene=4, tempo_bpm=301)


def test_accepts_complete_surface():
    spec = ToneSpec.model_validate(
        {
            "routing": {"mode": "serial", "chain": ["NG", "AMP", "IR"]},
            "modules": {"amp": {"model": "Brit 800", "parameters": {"gain": 62}}},
            "settings": {"midi": {"channel": 1}, "other": {"patch_tail": True}},
        }
    )
    assert spec.modules["amp"].parameters["gain"] == 62
