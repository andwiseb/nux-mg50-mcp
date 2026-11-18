from nux_mg50_mcp.bridge import UINode
from nux_mg50_mcp.driver import MockDriver, NuxAudioDriver
from nux_mg50_mcp.models import Operation, ToneSpec
from nux_mg50_mcp.planner import plan_tone


def test_mock_driver_dry_run_does_not_mutate():
    driver = MockDriver()
    result = driver.apply(plan_tone(ToneSpec(tempo_bpm=120)), dry_run=True)
    assert result["ok"]
    assert driver.snapshot()["operations"] == []


class SceneBridge:
    def click(self, _labels):
        return UINode(-1, "AXButton", "scene", "", "", 0, 0, 1, 1)


class TempoBridge(SceneBridge):
    def __init__(self):
        self.values: list[tuple[UINode, float, dict[str, float]]] = []

    def nodes(self):
        return [UINode(17, "AXTextField", "", "", "120", 700, 80, 60, 30)]

    def set_bounded_numeric_readout(self, node, value, **bounds):
        self.values.append((node, value, bounds))
        return node


class RoutingBridge(SceneBridge):
    def __init__(self):
        self.calls: list[tuple[object, ...]] = []

    def window(self):
        return UINode(0, "AXWindow", "", "", "", 10, 20, 800, 660)

    def run(self, *args):
        self.calls.append(args)
        return {"ok": True}

    def escape(self):
        self.calls.append(("escape",))


def test_chain_is_cleared_once_in_each_scene(monkeypatch):
    driver = NuxAudioDriver(SceneBridge())
    driver._routing_mode = "split_outputs"
    deleted: list[tuple[int, str]] = []

    monkeypatch.setattr(
        driver,
        "_delete_chain",
        lambda mode: deleted.append((driver._current_scene, mode)),
    )
    monkeypatch.setattr(
        driver,
        "_arrange_chain",
        lambda *_args: UINode(-1, "AXImage", "chain", "", "", 0, 0, 1, 1),
    )

    driver._apply_one(Operation(action="arrange", control="routing.chain_a", value=[]))
    driver._apply_one(Operation(action="arrange", control="routing.chain_b", value=[]))
    driver._apply_one(Operation(action="click", control="scene", value=2))
    driver._apply_one(Operation(action="arrange", control="routing.chain_a", value=[]))

    assert deleted == [(1, "split_outputs"), (2, "split_outputs")]


def test_non_setting_operation_closes_open_settings_page(monkeypatch):
    driver = NuxAudioDriver(SceneBridge())
    driver._page = "MIDI Setting"
    closed: list[str | None] = []

    def close_settings():
        closed.append(driver._page)
        driver._page = None

    monkeypatch.setattr(driver, "_close_settings", close_settings)
    driver._apply_one(Operation(action="click", control="scene", value=2))

    assert closed == ["MIDI Setting"]


def test_tempo_uses_committing_wheel_readout_instead_of_ax_value_write():
    bridge = TempoBridge()
    driver = NuxAudioDriver(bridge)

    driver._apply_one(Operation(action="set", control="tempo", value=124))

    assert [(node.index, value, bounds) for node, value, bounds in bridge.values] == [
        (17, 124, {"minimum": 40, "maximum": 240})
    ]


def test_routing_rows_match_the_observed_editor_order():
    bridge = RoutingBridge()
    driver = NuxAudioDriver(bridge)

    for mode in ("serial", "parallel_merge", "split_outputs"):
        driver._select_routing_mode(mode)

    assert bridge.calls == [
        ("select-routing", 0),
        ("select-routing", 1),
        ("select-routing", 2),
    ]


def test_add_module_retries_a_dropped_flutter_add(monkeypatch):
    bridge = RoutingBridge()
    driver = NuxAudioDriver(bridge)
    slot = (187.0, 158.0)
    clock = iter((0.0, 4.0, 5.0, 5.0))

    monkeypatch.setattr("nux_mg50_mcp.driver.time.monotonic", lambda: next(clock))
    monkeypatch.setattr("nux_mg50_mcp.driver.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(driver, "_refresh_slot_semantics", lambda _slot: None)
    monkeypatch.setattr(
        driver,
        "_chain_modules",
        lambda: [UINode(1, "AXImage", "DLY1", "", "", 168, 139, 38, 38)],
    )

    # Force the first attempt past its deadline, then let the second see DLY1.
    driver._add_chain_module(slot, "DLY")

    assert bridge.calls == [
        ("add-module", 187.0, 158.0, "DLY"),
        ("escape",),
        ("add-module", 187.0, 158.0, "DLY"),
    ]
