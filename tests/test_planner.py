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


def test_scene_local_work_defaults_deterministically_to_s1():
    plan = plan_tone(ToneSpec(tempo_bpm=120))
    assert [(op.control, op.value) for op in plan.operations[:2]] == [
        ("scene", 1),
        ("tempo", 120.0),
    ]

    settings_only = plan_tone(ToneSpec(settings={"midi": {"channel": 1}}))
    assert all(op.control != "scene" for op in settings_only.operations)


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
    assert [op.control for op in plan.operations].index("routing.chain") < [
        op.control for op in plan.operations
    ].index("stomp_assignments.A")


def test_explicit_empty_chain_is_planned_as_clear():
    plan = plan_tone(ToneSpec.model_validate({"routing": {"mode": "serial", "chain": []}}))
    assert any(op.action == "arrange" and op.control == "routing.chain" for op in plan.operations)


def test_stomp_state_is_planned_as_module_bypass():
    plan = plan_tone(
        ToneSpec.model_validate({"stomp": {"delay": False}, "scenes": {2: {"stomp": {"NG": True}}}})
    )
    rendered = [(op.control, op.value, op.scene) for op in plan.operations]
    assert ("DLY.enabled", False, None) in rendered
    assert ("NG.enabled", True, 2) in rendered


def test_all_settings_groups_are_planned():
    plan = plan_tone(
        ToneSpec.model_validate(
            {
                "settings": {
                    "output_mode": "Studio Direct(Line/Phones)",
                    "display": {"home_display": "graphical"},
                    "brightness": {"display": 50},
                    "parameter_follow": {"enabled": False},
                }
            }
        )
    )
    controls = {op.control for op in plan.operations}
    assert "settings.output_mode.mode" in controls
    assert "settings.display.home_display" in controls
    assert "settings.brightness.display" in controls
    assert "settings.parameter_follow.enabled" in controls


def test_explicit_scenes_inherit_base_chain_but_base_scene_is_not_rebuilt_twice():
    plan = plan_tone(
        ToneSpec.model_validate(
            {
                "scene": 1,
                "routing": {"mode": "serial", "chain": ["NG", "AMP", "DLY"]},
                "scenes": {
                    1: {"tempo_bpm": 121},
                    2: {"modules": {"AMP": {"parameters": {"gain": 32}}}},
                    3: {"stomp": {"DLY": False}},
                },
            }
        )
    )
    arrangements = [op for op in plan.operations if op.control == "routing.chain"]
    assert [(op.scene, op.value) for op in arrangements] == [
        (None, ["NG", "AMP", "DLY"]),
        (2, ["NG", "AMP", "DLY"]),
        (3, ["NG", "AMP", "DLY"]),
    ]


def test_scene_specific_routing_overrides_base_layout():
    plan = plan_tone(
        ToneSpec.model_validate(
            {
                "routing": {"mode": "serial", "chain": ["AMP"]},
                "scenes": {2: {"routing": {"mode": "serial", "chain": ["NG", "AMP"]}}},
            }
        )
    )
    scene_two = [op for op in plan.operations if op.scene == 2 and op.control == "routing.chain"]
    assert len(scene_two) == 1
    assert scene_two[0].value == ["NG", "AMP"]


def test_complete_plan_restores_base_scene_before_assignments_and_settings():
    plan = plan_tone(
        ToneSpec.model_validate(
            {
                "scene": 1,
                "routing": {"mode": "serial", "chain": ["AMP", "DLY"]},
                "scenes": {2: {"tempo_bpm": 122}, 3: {"tempo_bpm": 123}},
                "stomp_assignments": {"A": ["DLY"]},
                "settings": {"midi": {"channel": 1}},
                "preset_name": "MCP TEST",
                "save": True,
            }
        )
    )
    controls = [op.control for op in plan.operations]
    restore_index = max(
        index for index, op in enumerate(plan.operations) if op.control == "scene" and op.value == 1
    )
    assert restore_index > max(
        index
        for index, op in enumerate(plan.operations)
        if op.control == "scene" and op.value in {2, 3}
    )
    assert restore_index < controls.index("stomp_assignments.A")
    assert controls.index("stomp_assignments.A") < controls.index("settings.midi.channel")
    assert controls.index("settings.midi.channel") < controls.index("preset_name")
    assert controls[-1] == "preset"


def test_base_scene_routing_override_replaces_top_level_layout_once():
    plan = plan_tone(
        ToneSpec.model_validate(
            {
                "scene": 1,
                "routing": {"mode": "serial", "chain": ["AMP"]},
                "scenes": {
                    1: {"routing": {"mode": "serial", "chain": ["NG", "AMP"]}},
                    2: {},
                },
            }
        )
    )
    arrangements = [op for op in plan.operations if op.control == "routing.chain"]
    assert [(op.scene, op.value) for op in arrangements] == [
        (None, ["NG", "AMP"]),
        (2, ["AMP"]),
    ]
