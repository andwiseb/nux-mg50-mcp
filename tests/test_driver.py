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


class DoctorBridge(SceneBridge):
    def __init__(self, *, device_connected: bool):
        self.device_connected = device_connected

    def doctor(self):
        return {
            "appRunning": True,
            "accessibilityTrusted": True,
            "midiDeviceConnected": self.device_connected,
        }


def test_accessibility_driver_is_not_ready_without_a_connected_device():
    assert NuxAudioDriver(DoctorBridge(device_connected=False)).status()["ready"] is False


def test_accessibility_driver_requires_app_permission_and_device():
    status = NuxAudioDriver(DoctorBridge(device_connected=True)).status()
    assert status["ready"] is True


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


class PresetVolumeBridge(SceneBridge):
    def __init__(self):
        self.values = []

    def window(self):
        return UINode(0, "AXWindow", "", "", "", 10, 20, 800, 660)

    def nodes(self):
        return [
            UINode(2, "AXStaticText", "", "", "+0.0 dB", 650, 100, 60, 20),
            UINode(3, "AXStaticText", "", "", "0dB", 650, 400, 60, 20),
        ]

    def set_numeric_readout(self, node, value):
        self.values.append((node, value))
        return node


def test_arrange_chain_keeps_matching_slots_without_ui_mutation(monkeypatch):
    driver = NuxAudioDriver(SceneBridge())
    slots = [(100.0, 100.0), (200.0, 100.0), (300.0, 100.0)]
    current = [
        UINode(1, "AXImage", "AMP1", "", "", 81, 81, 38, 38),
        UINode(2, "AXImage", "CMP1", "", "", 181, 81, 38, 38),
        UINode(3, "AXImage", "RVB1", "", "", 281, 81, 38, 38),
    ]
    deleted: list[str] = []
    added: list[tuple[tuple[float, float], str]] = []
    monkeypatch.setattr(driver, "_routing_slots", lambda *_args: slots)
    monkeypatch.setattr(driver, "_chain_modules", lambda: current)
    monkeypatch.setattr(driver, "_delete_module", lambda node: deleted.append(node.title))
    monkeypatch.setattr(driver, "_add_chain_module", lambda slot, name: added.append((slot, name)))

    result = driver._arrange_chain("routing.chain", ["AMP", "CMP", "RVB"], "serial")

    assert result.title == "RVB1"
    assert deleted == []
    assert added == []


def test_arrange_chain_replaces_only_mismatching_slot(monkeypatch):
    driver = NuxAudioDriver(SceneBridge())
    slots = [(100.0, 100.0), (200.0, 100.0), (300.0, 100.0)]
    current = [
        UINode(1, "AXImage", "AMP1", "", "", 81, 81, 38, 38),
        UINode(2, "AXImage", "CMP1", "", "", 181, 81, 38, 38),
        UINode(3, "AXImage", "RVB1", "", "", 281, 81, 38, 38),
    ]
    deleted: list[str] = []
    added: list[tuple[tuple[float, float], str]] = []
    monkeypatch.setattr(driver, "_routing_slots", lambda *_args: slots)
    monkeypatch.setattr(driver, "_chain_modules", lambda: current)
    monkeypatch.setattr(driver, "_delete_module", lambda node: deleted.append(node.title))
    monkeypatch.setattr(driver, "_add_chain_module", lambda slot, name: added.append((slot, name)))
    monkeypatch.setattr(
        driver,
        "_find_chain_module_wait",
        lambda name: UINode(4, "AXImage", f"{name}1", "", "", 181, 81, 38, 38),
    )

    driver._arrange_chain("routing.chain", ["AMP", "MOD", "RVB"], "serial")

    assert deleted == ["CMP1"]
    assert added == [((200.0, 100.0), "MOD")]


def test_arrange_chain_removes_only_trailing_modules(monkeypatch):
    driver = NuxAudioDriver(SceneBridge())
    slots = [(100.0, 100.0), (200.0, 100.0), (300.0, 100.0)]
    current = [
        UINode(1, "AXImage", "AMP1", "", "", 81, 81, 38, 38),
        UINode(2, "AXImage", "CMP1", "", "", 181, 81, 38, 38),
        UINode(3, "AXImage", "RVB1", "", "", 281, 81, 38, 38),
    ]
    deleted: list[str] = []
    added: list[tuple[tuple[float, float], str]] = []
    monkeypatch.setattr(driver, "_routing_slots", lambda *_args: slots)
    monkeypatch.setattr(driver, "_chain_modules", lambda: current)
    monkeypatch.setattr(driver, "_delete_module", lambda node: deleted.append(node.title))
    monkeypatch.setattr(driver, "_add_chain_module", lambda slot, name: added.append((slot, name)))

    result = driver._arrange_chain("routing.chain", ["AMP", "CMP"], "serial")

    assert result.title == "CMP1"
    assert deleted == ["RVB1"]
    assert added == []


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


def test_preset_volume_uses_top_level_firmware_readout():
    bridge = PresetVolumeBridge()
    driver = NuxAudioDriver(bridge)

    driver._apply_one(Operation(action="set", control="preset_volume", value=-1.5))

    assert [(node.index, value) for node, value in bridge.values] == [(2, -1.5)]


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
