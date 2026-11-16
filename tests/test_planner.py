from nux_mg50_mcp.models import ToneSpec
from nux_mg50_mcp.planner import plan_tone


def test_plan_orders_preset_scene_module_and_save():
    spec = ToneSpec.model_validate(
        {
            "preset": "43A",
            "scene": 2,
            "modules": {"amp": {"model": "Brit 800", "enabled": True, "parameters": {"gain": 61}}},
            "save": True,
        }
    )
    plan = plan_tone(spec)
    assert [(op.action, op.control) for op in plan.operations] == [
        ("select", "preset"),
        ("click", "scene"),
        ("click", "module"),
        ("select", "AMP.model"),
        ("toggle", "AMP.enabled"),
        ("set", "AMP.gain"),
        ("save", "preset"),
    ]


def test_unsaved_plan_warns():
    assert "not saved" in plan_tone(ToneSpec()).warnings[0]


def test_stomp_assignments_and_chain_are_explicit_operations():
    spec = ToneSpec.model_validate(
        {
            "stomp_assignments": {"A": ["EFX", "DLY"], "B": []},
            "routing": {"mode": "serial", "chain": ["EFX", "AMP", "IR"]},
        }
    )
    plan = plan_tone(spec)
    rendered = [(op.action, op.control, op.value) for op in plan.operations]
    assert ("assign", "stomp_assignments.A", ["EFX", "DLY"]) in rendered
    assert ("assign", "stomp_assignments.B", []) in rendered
    assert ("arrange", "routing.chain", ["EFX", "AMP", "IR"]) in rendered
