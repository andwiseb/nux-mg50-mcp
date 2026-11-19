from __future__ import annotations

import math
import re
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from .bridge import AccessibilityBridge, UINode, _norm
from .catalog import MODULE_ALIASES, canonical_module
from .errors import BridgeError, ControlNotFound
from .models import ApplyPlan, Operation


class Driver(ABC):
    @abstractmethod
    def status(self) -> dict[str, Any]: ...

    @abstractmethod
    def snapshot(self) -> dict[str, Any]: ...

    @abstractmethod
    def apply(self, plan: ApplyPlan, *, dry_run: bool = False) -> dict[str, Any]: ...


class MockDriver(Driver):
    """Deterministic driver used by tests and `NUX_DRIVER=mock` demos."""

    def __init__(self) -> None:
        self.operations: list[dict[str, Any]] = []

    def status(self) -> dict[str, Any]:
        return {"driver": "mock", "ready": True}

    def snapshot(self) -> dict[str, Any]:
        return {"driver": "mock", "operations": self.operations}

    def apply(self, plan: ApplyPlan, *, dry_run: bool = False) -> dict[str, Any]:
        rendered = [operation.model_dump() for operation in plan.operations]
        if not dry_run:
            self.operations.extend(rendered)
        return {"ok": True, "dry_run": dry_run, "operations": rendered, "warnings": plan.warnings}


class NuxAudioDriver(Driver):
    """NUX Audio automation driven by semantic accessibility labels."""

    LABELS: ClassVar[dict[str, tuple[str, ...]]] = {
        "scene": ("Scene", "SCENE"),
        "tempo": ("Tempo", "TAP", "BPM"),
        "preset": ("Preset", "PRESET"),
        "preset_name": ("Preset name",),
        "save": ("Save Preset", "Save", "SAVE"),
    }

    def __init__(self, bridge: AccessibilityBridge | None = None) -> None:
        self.bridge = bridge or AccessibilityBridge()
        self._page: str | None = None
        self._rebuilt_modules: set[str] = set()
        self._module_slots: dict[str, list[UINode]] = {}
        self._module_states: dict[tuple[int, str], bool] = {}
        self._current_scene = 1
        self._cleared_scenes: set[int] = set()

    def _open_page(self, name: str) -> None:
        if self._page == name:
            return
        self.bridge.open_more_menu()
        time.sleep(0.25)
        self.bridge.click_wait(name, timeout=2.0)
        time.sleep(0.2)
        self._page = name

    def _open_settings_page(self, page: str) -> None:
        settings_pages = {
            "Settings",
            "Input Trim",
            "Output Mode",
            "Global Eq",
            "Display",
            "Brightness",
            "Para.Follow",
            "Console",
            "MIDI Setting",
            "Other",
        }
        if self._page not in settings_pages:
            self._open_page("Settings")
        if self._page != page:
            self.bridge.click((page, page.replace(" ", "")))
            time.sleep(0.3)
            self._page = page

    def _close_settings(self) -> None:
        if self._page in {
            "Settings",
            "Input Trim",
            "Output Mode",
            "Global Eq",
            "Global EQ",
            "Display",
            "Brightness",
            "Para.Follow",
            "Console",
            "MIDI Setting",
            "Other",
        }:
            # Settings is opened from the More route; dismissing only the modal
            # leaves that menu over the editor. The Home icon pops both layers.
            self._relative_click(24, 55)
            self._page = None

    def _relative_click(self, x: float, y: float) -> UINode:
        window = self.bridge.window()
        self.bridge.click_point(window.x + x, window.y + y)
        return UINode(-1, "AXPoint", "", "", "", window.x + x, window.y + y, 0, 0)

    def _relative_drag(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> UINode:
        window = self.bridge.window()
        source = (window.x + start[0], window.y + start[1])
        target = (window.x + end[0], window.y + end[1])
        self.bridge.drag_points(source, target)
        return UINode(-1, "AXPoint", "", "", "", target[0], target[1], 0, 0)

    def _set_horizontal_switch(self, x: float, y: float, right: bool) -> UINode:
        return self._relative_drag((x, y), (x + (15 if right else -15), y))

    def _set_vertical_switch(self, x: float, y: float, top: bool) -> UINode:
        return self._relative_drag((x, y), (x, y + (-15 if top else 15)))

    def _set_labeled_toggle(self, x: float, y: float, desired: bool) -> UINode:
        window = self.bridge.window()
        buttons = [
            node
            for node in self.bridge.nodes()
            if node.role == "AXButton"
            and _norm(node.text) in {"on", "off"}
            and abs((node.x + node.width / 2) - (window.x + x)) <= 25
            and abs((node.y + node.height / 2) - (window.y + y)) <= 25
        ]
        if not buttons:
            raise ControlNotFound("stateful ON/OFF button not found")
        button = min(
            buttons,
            key=lambda node: abs((node.x + node.width / 2) - (window.x + x)),
        )
        current = _norm(button.text) == "on"
        if current != desired:
            self.bridge.click_point(button.x + button.width / 2, button.y + button.height / 2)
        return button

    def _apply_setting(self, group: str, parameter: str, value: object) -> UINode:
        key = _norm(parameter)
        pages = {
            "input_trim": "Input Trim",
            "output_mode": "Output Mode",
            "global_eq": "Global Eq",
            "display": "Display",
            "brightness": "Brightness",
            "parameter_follow": "Para.Follow",
            "output_console": "Console",
            "midi": "MIDI Setting",
            "other": "Other",
        }
        self._open_settings_page(pages[group])

        if group == "input_trim":
            return self.bridge.set_parameter(parameter, value)
        if group == "output_mode":
            return self.bridge.click(str(value))
        if group == "display":
            choices = {
                "homedisplay": {"graphical": (387, 309), "number": (546, 309), "name": (546, 309)},
                "bootuppicture": {"factory": (387, 464), "user": (546, 464)},
            }
            option = _norm(value)
            if key not in choices or option not in choices[key]:
                raise BridgeError(f"unsupported display setting {parameter}={value!r}")
            return self._relative_click(*choices[key][option])
        if group == "brightness":
            y_by_key = {"display": 355, "footswitch": 400, "pedal": 400}
            if key not in y_by_key:
                raise BridgeError(f"unsupported brightness control: {parameter}")
            level = max(0, min(100, int(value)))
            return self._relative_click(307 + 3.09 * level, y_by_key[key])
        if group == "parameter_follow":
            desired = bool(value)
            if key in {"enabled", "parameterfollow", "parafollow"}:
                return self._set_vertical_switch(628, 357, top=desired)
            if key in {"ampconnectsdefaultir", "defaultir"}:
                return self._set_horizontal_switch(543, 451, right=desired)
            raise BridgeError(f"unsupported parameter-follow control: {parameter}")
        if group == "global_eq":
            if key in {"enabled", "on"}:
                return self._set_labeled_toggle(304, 275, bool(value))
            if key in {"lpfenabled", "lpfon"}:
                return self._set_labeled_toggle(598, 275, bool(value))
            x_by_key = {
                "hpf": 304,
                "100": 349,
                "200": 382,
                "500": 415,
                "12k": 448,
                "26k": 481,
                "64k": 514,
                "10k": 547,
                "lpf": 598,
                "level": 635,
            }
            if key not in x_by_key:
                raise BridgeError(f"unsupported Global EQ control: {parameter}")
            number = float(value)
            if key == "hpf":
                ratio = (math.log(max(20, min(1000, number))) - math.log(20)) / (
                    math.log(1000) - math.log(20)
                )
            elif key == "lpf":
                ratio = (math.log(max(5, min(20000, number))) - math.log(5)) / (
                    math.log(20000) - math.log(5)
                )
            else:
                ratio = (max(-12, min(12, number)) + 12) / 24
            return self._relative_click(x_by_key[key], 461 - 162 * ratio)
        if group == "output_console":
            slider_x = {"phones": 310, "output": 392, "xlr": 473, "usbin12": 554, "usbin34": 635}
            if key in slider_x:
                number = float(value)
                maximum = 12 if key == "usbin34" else 100
                ratio = (max(0, min(maximum, number))) / maximum
                return self._relative_click(slider_x[key], 358 - 117 * ratio)
            mute_x = {
                "phonesmute": 310,
                "outputmute": 392,
                "xlrmute": 473,
                "usbin12mute": 554,
                "usbin34mute": 635,
            }
            if key in mute_x:
                window = self.bridge.window()
                buttons = sorted(
                    (
                        node
                        for node in self.bridge.nodes()
                        if node.role == "AXButton"
                        and _norm(node.text).startswith("mute")
                        and window.x + 250 <= node.x <= window.x + 680
                        and window.y + 190 <= node.y <= window.y + 240
                    ),
                    key=lambda node: node.x,
                )
                ordinal = list(mute_x).index(key)
                if len(buttons) != 5:
                    raise ControlNotFound("five Console Mute buttons were not found")
                button = buttons[ordinal]
                red, green, blue = self.bridge.sample_color(button)
                current = red - max(green, blue) > 0.08
                if current != bool(value):
                    self.bridge.click_point(
                        button.x + button.width / 2, button.y + button.height / 2
                    )
                return button
            if key == "inputmonitor":
                readout = self.bridge.find("50", roles={"AXStaticText"})
                return self.bridge.set_numeric_readout(readout, value)
            if key == "usbmode":
                return self._set_vertical_switch(304, 483, top=_norm(value) == "normal")
            if key == "dryin":
                return self._set_vertical_switch(
                    503, 483, top=_norm(value) in {"usbin34", "usbin3/4"}
                )
            if key == "loopback":
                return self._set_vertical_switch(590, 483, top=bool(value))
            raise BridgeError(f"unsupported Console control: {parameter}")
        if group == "midi":
            if key == "channel":
                numeric = [
                    node
                    for node in self.bridge.nodes()
                    if node.role == "AXStaticText" and re.fullmatch(r"\d{2}", node.text)
                ]
                if not numeric:
                    raise ControlNotFound("MIDI channel readout not found")
                return self.bridge.set_numeric_readout(numeric[0], int(value))
            if key == "midiin":
                return self._set_vertical_switch(424, 376, top=bool(value))
            if key == "midiout":
                return self._set_vertical_switch(497, 376, top=bool(value))
            if key in {"programchange", "program"}:
                return self.bridge.click(str(value).upper())
            raise BridgeError(f"unsupported MIDI control: {parameter}")
        if group == "other":
            switches = {
                "s3scene": (539, 243, {"on": True, "off": False}),
                "tap": (539, 281, {"global": True, "preset": False}),
                "phones": (539, 320, {"xlr": True, "output": False}),
                "patchrolling": (539, 358, {"ccw": True, "cw": False}),
                "patchtail": (539, 396, {"on": True, "off": False}),
            }
            if key in switches:
                x, y, options = switches[key]
                option = _norm(value)
                desired = bool(value) if isinstance(value, bool) else options.get(option)
                if desired is None:
                    raise BridgeError(f"unsupported Other setting {parameter}={value!r}")
                return self._set_horizontal_switch(x, y, right=desired)
            if key == "language":
                return self.bridge.click(str(value))
            raise BridgeError(f"unsupported Other control: {parameter}")
        raise BridgeError(f"unsupported settings group: {group}")

    @staticmethod
    def _module_menu_label(name: str) -> str:
        canonical = canonical_module(name)
        return {"NG": "GATE", "PL": "PL", "AMP2": "AMP"}.get(canonical, canonical)

    def _stomp_modules(self, window: UINode) -> list[UINode]:
        """Return blocks from the Stomp modal, excluding the chain behind it."""
        return [
            node
            for node in self.bridge.nodes()
            if node.text
            and node.role in {"AXImage", "AXGroup"}
            and 28 <= node.width <= 48
            and 28 <= node.height <= 48
            and window.y + 250 <= node.y + node.height / 2 <= window.y + 415
        ]

    def _refresh_stomp_semantics(self, window: UINode) -> None:
        """Visit modal slots so Flutter publishes every occupied block label."""
        points = [(157 + 68.5 * index, 294) for index in range(7)]
        points += [(225.5 + 68.5 * index, 374) for index in range(7)]
        for x, y in points:
            self.bridge.click_point(window.x + x, window.y + y)

    def _stomp_point_from_chain(self, window: UINode, module: str) -> tuple[float, float] | None:
        known = self._module_slots.get(canonical_module(module), [])
        if not known:
            return None
        main = known[0]
        main_x = main.x + main.width / 2 - window.x
        main_y = main.y + main.height / 2 - window.y
        modal_x = 157 + (main_x - 187) * (68.5 / 73.5)
        modal_y = 294 if main_y < 186 else 374
        return window.x + modal_x, window.y + modal_y

    def _find_stomp_module(self, window: UINode, module: str) -> UINode:
        wanted = _norm(self._module_menu_label(module))
        for node in self._stomp_modules(window):
            base = _norm(node.text.splitlines()[0]).rstrip("0123456789")
            if base == wanted:
                return node
        fallback = self._stomp_point_from_chain(window, module)
        if fallback is not None:
            return UINode(
                index=-1,
                role="AXImage",
                title=self._module_menu_label(module),
                description="",
                value="",
                x=fallback[0] - 19,
                y=fallback[1] - 19,
                width=38,
                height=38,
            )
        raise ControlNotFound(f"module {module!r} is not present in the Stomp assignment modal")

    def _chain_modules(self) -> list[UINode]:
        nodes = self.bridge.nodes()
        window = next((node for node in nodes if node.role == "AXWindow"), None)
        if window is None:
            return []
        aliases = {_norm(alias) for values in MODULE_ALIASES.values() for alias in values}
        aliases.update({"ampimage", "poweramp"})
        result = []
        for node in nodes:
            center_y = node.y + node.height / 2
            text = _norm(node.title or node.description or node.value).rstrip("0123456789")
            if (
                window.x + 130 <= node.x <= window.x + window.width - 70
                and window.y + 125 <= center_y <= window.y + 235
                and 30 <= node.width <= 45
                and text in aliases
            ):
                result.append(node)
        return result

    def _find_chain_module(self, name: str) -> UINode:
        canonical = canonical_module(name)
        aliases = {_norm(alias) for alias in MODULE_ALIASES.get(canonical, (canonical,))}
        aliases.add(_norm(canonical))
        for node in self._chain_modules():
            value = _norm(node.title or node.description or node.value).rstrip("0123456789")
            if value in aliases or (canonical == "AMP2" and value == "amp"):
                return node
        # Flutter occasionally paints a newly-added module but omits that block
        # from the semantics tree of subsequent AX clients.  Arranged modules
        # retain a stable slot coordinate, which is sufficient for selection,
        # bypass and deletion even when the optional label is absent.
        known = self._module_slots.get(canonical, [])
        if known:
            return known[0]
        raise ControlNotFound(f"module {name!r} is not present in the signal chain")

    def _find_chain_module_wait(self, name: str, timeout: float = 2.0) -> UINode:
        deadline = time.monotonic() + timeout
        last_error: ControlNotFound | None = None
        while time.monotonic() < deadline:
            try:
                return self._find_chain_module(name)
            except ControlNotFound as error:
                last_error = error
                time.sleep(0.1)
        assert last_error is not None
        raise last_error

    def _select_chain_module(self, name: str) -> UINode:
        node = self._find_chain_module(name)
        if node.index < 0:
            self.bridge.run(
                "select-module-at",
                node.x + node.width / 2,
                node.y + node.height / 2,
                self._module_menu_label(name),
            )
        else:
            label = node.title or node.description or node.value
            self.bridge.run("press-label", label)
        time.sleep(0.35)
        return node

    def _refresh_slot_semantics(self, slot: tuple[float, float]) -> None:
        """Make Flutter publish a chain block to a fresh AX client.

        A harmless context-menu open/close causes Flutter 3's semantics owner to
        materialize a painted block that may otherwise be absent from snapshots.
        Empty slots simply ignore the secondary click.
        """
        self.bridge.run("right-click-screen", slot[0], slot[1])
        self.bridge.escape()
        time.sleep(0.08)

    def _delete_chain(self, mode: str) -> None:
        # Re-query after each deletion because Flutter rebuilds and reindexes the tree.
        slots = self._routing_slots(mode, "a")
        if mode != "serial":
            slots += self._routing_slots(mode, "b")
        for _ in range(14):
            modules = self._chain_modules()
            if not modules:
                for slot in slots:
                    self._refresh_slot_semantics(slot)
                    modules = self._chain_modules()
                    if modules:
                        break
            if not modules:
                return
            target = modules[0]
            point = (target.x + target.width / 2, target.y + target.height / 2)
            last_error: BridgeError | None = None
            for _attempt in range(3):
                try:
                    self.bridge.run("delete-at", point[0], point[1])
                    last_error = None
                    break
                except BridgeError as error:
                    last_error = error
            if last_error is not None:
                raise ControlNotFound(
                    "module context-menu Delete action did not open"
                ) from last_error
        if self._chain_modules():
            raise BridgeError("could not clear the existing signal chain")

    def _delete_module(self, target: UINode) -> None:
        """Delete exactly one visible chain block, retrying only its own menu action."""
        point = (target.x + target.width / 2, target.y + target.height / 2)
        last_error: BridgeError | None = None
        for _attempt in range(3):
            try:
                self.bridge.run("delete-at", point[0], point[1])
                return
            except BridgeError as error:
                last_error = error
        raise ControlNotFound("module context-menu Delete action did not open") from last_error

    def _select_routing_mode(self, mode: str) -> UINode:
        window = self.bridge.window()
        # NUX Audio order: serial, parallel split + merge, split to OUT/XLR.
        row = {"serial": 0, "parallel_merge": 1, "split_outputs": 2}[str(mode)]
        self.bridge.run("select-routing", row)
        return UINode(
            -1,
            "AXPoint",
            "routing",
            "",
            str(mode),
            window.x + 116.5,
            window.y + [205, 242, 279.5][row],
            0,
            0,
        )

    def _routing_slots(self, mode: str, branch: str) -> list[tuple[float, float]]:
        window = self.bridge.window()
        # Slot centres (not their left edges) in the fixed 800x660 editor.
        xs_top = [187, 260, 333.5, 407, 480.5, 554, 627]
        xs_split = [260, 333.5, 407, 480.5, 554, 627, 700.5]
        top_y = 158
        bottom_y = 214
        if mode == "serial":
            # The serial layout snakes across row one, then right-to-left on row two.
            raw = [(x, top_y) for x in xs_top]
            raw += [(x, bottom_y) for x in reversed(xs_split)]
        elif mode == "parallel_merge":
            xs = xs_split[:-1]
            raw = [(x, top_y) for x in xs] if branch == "a" else [(x, bottom_y) for x in xs]
        else:
            raw = (
                [(x, top_y) for x in xs_split]
                if branch == "a"
                else [(x, bottom_y) for x in xs_split]
            )
        return [(window.x + x, window.y + y) for x, y in raw]

    def _press_near(self, point: tuple[float, float], radius: float = 45) -> UINode:
        x, y = point
        candidates = [
            node
            for node in self.bridge.nodes()
            if node.role in {"AXImage", "AXGroup", "AXButton"}
            and 20 <= node.width <= 60
            and 20 <= node.height <= 60
            and abs((node.x + node.width / 2) - x) <= radius
            and abs((node.y + node.height / 2) - y) <= radius
        ]
        if not candidates:
            raise ControlNotFound(f"pressable control near ({x:.0f}, {y:.0f}) was not found")
        node = min(
            candidates,
            key=lambda item: (
                ((item.x + item.width / 2) - x) ** 2 + ((item.y + item.height / 2) - y) ** 2
            ),
        )
        self.bridge.click_point(node.x + node.width / 2, node.y + node.height / 2)
        return node

    def _add_chain_module(self, slot: tuple[float, float], module: str) -> None:
        label = self._module_menu_label(module)
        canonical = canonical_module(module)
        aliases = {_norm(alias) for alias in MODULE_ALIASES.get(canonical, (canonical,))}
        aliases.add(_norm(canonical))
        for attempt in range(2):
            self.bridge.run("add-module", slot[0], slot[1], label)
            self._refresh_slot_semantics(slot)
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                matches = [
                    node
                    for node in self._chain_modules()
                    if abs((node.x + node.width / 2) - slot[0]) <= 10
                    and abs((node.y + node.height / 2) - slot[1]) <= 10
                    and _norm(node.title or node.description or node.value).rstrip("0123456789")
                    in aliases
                ]
                if matches:
                    self._module_slots.setdefault(canonical, []).append(
                        UINode(
                            index=-1,
                            role="AXImage",
                            title=label,
                            description="",
                            value="",
                            x=slot[0] - 19,
                            y=slot[1] - 19,
                            width=38,
                            height=38,
                        )
                    )
                    self._module_states[(self._current_scene, canonical)] = True
                    return
                time.sleep(0.1)
            if attempt == 0:
                # Flutter occasionally drops the Add press after many modal
                # transactions. A second full transaction is safe because the
                # requested slot is still verified empty above.
                self.bridge.escape()
                time.sleep(0.2)
        raise ControlNotFound(f"module {module!r} did not occupy its requested chain slot")

    def _arrange_chain(self, control: str, modules: list[str], mode: str) -> UINode:
        branch = "b" if control.endswith("chain_b") else "a"
        slots = self._routing_slots(mode, branch)
        if len(modules) > len(slots):
            raise BridgeError(f"{control} accepts at most {len(slots)} modules in {mode} mode")

        desired = [canonical_module(module) for module in modules]
        occupied: dict[int, tuple[UINode, str]] = {}
        for node in self._chain_modules():
            center = (node.x + node.width / 2, node.y + node.height / 2)
            distances = [(center[0] - slot[0]) ** 2 + (center[1] - slot[1]) ** 2 for slot in slots]
            if not distances:
                continue
            index = min(range(len(distances)), key=distances.__getitem__)
            if distances[index] > 12**2:
                continue
            label = node.title or node.description or node.value
            occupied[index] = (node, canonical_module(label.rstrip("0123456789")))

        # Fixed chain slots do not need a full destructive rebuild. Preserve exact
        # matches, delete only mismatches/extras, then fill only the resulting holes.
        mismatches = [
            index
            for index, (_node, current) in occupied.items()
            if index >= len(desired) or current != desired[index]
        ]
        for index in sorted(mismatches, reverse=True):
            self._delete_module(occupied[index][0])
            occupied.pop(index)

        last: UINode | None = None
        for index, (module, canonical) in enumerate(zip(modules, desired, strict=True)):
            existing = occupied.get(index)
            if existing is not None and existing[1] == canonical:
                last = existing[0]
                continue
            slot = slots[index]
            self._add_chain_module(slot, module)
            last = self._find_chain_module_wait(module)
            self._rebuilt_modules.add(canonical)
        return last or self.bridge.find("Chain")

    def status(self) -> dict[str, Any]:
        result = self.bridge.doctor()
        result["driver"] = "nux-audio-accessibility"
        result["ready"] = bool(
            result.get("midiDeviceConnected")
            and result.get("appRunning")
            and result.get("accessibilityTrusted")
        )
        return result

    def snapshot(self) -> dict[str, Any]:
        return self.bridge.snapshot()

    def _apply_one(self, operation: Operation) -> dict[str, Any]:
        control = operation.control
        if not control.startswith("settings."):
            self._close_settings()
        if operation.action == "save":
            self.bridge.open_more_menu()
            time.sleep(0.25)
            node = self.bridge.click_wait(self.LABELS["save"], timeout=2.0)
        elif control == "scene":
            node = self.bridge.click((f"S{operation.value}", f"Scene {operation.value}"))
            self._current_scene = int(operation.value)
            self._rebuilt_modules.clear()
            self._module_slots.clear()
        elif control == "preset":
            nodes = self.bridge.nodes()
            current = next(
                (item for item in nodes if re.fullmatch(r"\d{1,2}[ABC]", item.text.strip())), None
            )
            node = current or self.bridge.find(self.LABELS["preset"])
            # Keep the entire Flutter modal transaction inside one native process;
            # otherwise its lazily-built semantics indices change between calls.
            self.bridge.run("select-preset", node.index, operation.value)
        elif control == "preset_name":
            fields = [
                item
                for item in self.bridge.nodes()
                if item.role == "AXTextField" and item.width > 100
            ]
            if not fields:
                raise ControlNotFound("preset name text field not found")
            node = max(fields, key=lambda item: item.width)
            self.bridge.run("set-snapshot", node.index, operation.value)
        elif control == "preset_volume":
            window = self.bridge.window()
            candidates = [
                item
                for item in self.bridge.nodes()
                if item.role == "AXStaticText"
                and re.fullmatch(r"[+-]?\d+(?:\.\d+)?\s*dB", item.text.strip(), re.IGNORECASE)
                and window.y + 50 <= item.y <= window.y + 180
            ]
            if not candidates:
                raise ControlNotFound(
                    "preset volume readout not found; this control requires MG-50Li "
                    "firmware/editor support that exposes the ±12 dB value"
                )
            node = self.bridge.set_numeric_readout(candidates[0], operation.value)
        elif control == "tempo":
            fields = [
                item
                for item in self.bridge.nodes()
                if item.role == "AXTextField" and item.width < 100
            ]
            if not fields:
                raise ControlNotFound("tempo text field not found")
            node = max(fields, key=lambda item: item.x)
            # Flutter accepts AXValue writes but does not send them to the pedal;
            # the semantic value can change while the painted/device BPM stays put.
            # Wheel steps are the editor's real commit path, just like knob readouts.
            self.bridge.set_bounded_numeric_readout(
                node,
                operation.value,
                minimum=40,
                maximum=240,
            )
        elif control == "module":
            node = self._select_chain_module(str(operation.value))
            # AXPress updates Flutter's selected-module semantics for all AX
            # clients; a raw CG click can update the pixels while leaving a new
            # client on the previously selected parameter strip.
            self._page = "home"
        elif control.startswith("settings."):
            _, group, parameter = control.split(".", 2)
            node = self._apply_setting(group, parameter, operation.value)
        elif operation.action == "assign":
            switch = control.rsplit(".", 1)[-1]
            self._open_page("Stomp")
            window = self.bridge.window()
            self._refresh_stomp_semantics(window)
            switch_x = {"A": 295, "B": 361, "C": 423}[switch]
            requested = {canonical_module(str(module)) for module in operation.value}
            # Remove stale assignments for this switch, making repeated applies
            # deterministic instead of merely adding to the current preset.
            for existing in self._stomp_modules(window):
                lines = [line.strip() for line in existing.text.splitlines() if line.strip()]
                base = lines[0].rstrip("0123456789")
                try:
                    canonical = canonical_module(base)
                except ValueError:
                    continue
                if switch in lines[1:] and canonical not in requested:
                    self.bridge.click_point(
                        existing.x + existing.width / 2,
                        existing.y + existing.height / 2,
                    )
                    self.bridge.click("UNASSIGN")
            node = self.bridge.find("UNASSIGN")
            for module in operation.value:
                assigned = self._find_stomp_module(window, str(module))
                lines = [line.strip() for line in assigned.text.splitlines() if line.strip()]
                if switch not in lines[1:]:
                    self.bridge.click_point(
                        assigned.x + assigned.width / 2,
                        assigned.y + assigned.height / 2,
                    )
                    self.bridge.click_point(window.x + switch_x, window.y + 449)
                node = assigned
            self.bridge.escape()
            self._page = None
        elif operation.action == "arrange":
            mode = getattr(self, "_routing_mode", "serial")
            node = self._arrange_chain(control, list(operation.value), mode)
        elif control in {"routing.split_mode", "routing.a_level", "routing.b_level"}:
            if control == "routing.split_mode":
                window = self.bridge.window()
                desired = str(operation.value)
                splitter = self._press_near((window.x + 187, window.y + 158))
                time.sleep(0.25)
                # The editor uses a vertical selector: upper position is DUAL,
                # lower position is per-chain A/B editing.
                y = window.y + (311 if desired == "dual" else 348)
                self.bridge.click_point(window.x + 382, y)
                time.sleep(0.2)
                node = splitter
            else:
                nodes = self.bridge.nodes()
                strip = next(
                    (item for item in nodes if "A LEVEL" in item.text and "B LEVEL" in item.text),
                    None,
                )
                if strip is None:
                    raise ControlNotFound("split A/B level control group not found")
                numeric = sorted(
                    (
                        item
                        for item in nodes
                        if item.index != strip.index
                        and self.bridge._number(item) is not None
                        and strip.x <= item.x + item.width / 2 <= strip.x + strip.width
                        and strip.y <= item.y + item.height / 2 <= strip.y + strip.height
                    ),
                    key=lambda item: item.x,
                )
                if len(numeric) < 2:
                    raise ControlNotFound("split A/B numeric readouts not found")
                ordinal = 0 if control.endswith("a_level") else 1
                node = self.bridge.set_numeric_readout(numeric[ordinal], operation.value)
        elif operation.action == "select":
            # Open a selector (model/routing), then choose the requested visible option.
            if control.endswith(".model"):
                nodes = self.bridge.nodes()
                label = self.bridge.find("Model")
                candidates = [
                    item
                    for item in nodes
                    if item.index < label.index and item.role.endswith("Image") and item.text
                ]
                opener = max(candidates, key=lambda item: item.index) if candidates else label
                self.bridge.click_point(opener.x + opener.width / 2, opener.y + opener.height / 2)
            elif control == "routing.mode":
                node = self._select_routing_mode(str(operation.value))
                self._routing_mode = str(operation.value)
                return {"operation": operation.model_dump(), "node": node.__dict__}
            else:
                self.bridge.click((control, control.split(".")[-1], control.replace(".", " ")))
            node = self.bridge.click(str(operation.value))
            if control.endswith(".model"):
                # Model selectors are Flutter modal routes; let the parameter
                # strip for the new model replace the route before the next op.
                time.sleep(0.35)
        elif operation.action == "toggle":
            if control.endswith(".enabled"):
                module = control.split(".", 1)[0]
                desired = bool(operation.value)
                canonical = canonical_module(module)
                node = self._find_chain_module(module)
                state_key = (self._current_scene, canonical)
                current = self._module_states.get(state_key)
                if current is None:
                    red, green, blue = self.bridge.sample_color(node)
                    current = max(red, green, blue) - min(red, green, blue) > 0.06
                if current != desired:
                    self.bridge.right_click(node)
                    self.bridge.click("ON/OFF")
                self._module_states[state_key] = desired
                return {"operation": operation.model_dump(), "node": node.__dict__}
            labels = (control, control.split(".")[-1], control.replace(".", " "))
            node = self.bridge.find(labels)
            current = node.value.casefold().strip()
            desired = bool(operation.value)
            known_true = current in {"1", "true", "on", "yes", "checked", "enabled"}
            known_false = current in {"0", "false", "off", "no", "unchecked", "disabled"}
            if not ((desired and known_true) or (not desired and known_false)):
                self.bridge.click_point(node.x + node.width / 2, node.y + node.height / 2)
        else:
            # The last component is normally the exact visible knob/switch label.
            parameter = control.split(".", 1)[1] if "." in control else control
            labels = (control, parameter, control.replace(".", " "))
            if operation.action == "click":
                node = self.bridge.click(labels)
            else:
                module_name = control.split(".", 1)[0]
                if canonical_module(module_name) in MODULE_ALIASES:
                    self._select_chain_module(module_name)
                node = self.bridge.set_parameter(parameter, operation.value)
        return {"operation": operation.model_dump(), "node": node.__dict__}

    def apply(self, plan: ApplyPlan, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "operations": [op.model_dump() for op in plan.operations],
                "warnings": plan.warnings,
            }
        status = self.status()
        if not status["ready"]:
            return {"ok": False, "status": status, "operations": [], "warnings": plan.warnings}
        self.bridge.activate()
        time.sleep(0.25)
        self._cleared_scenes.clear()
        self._rebuilt_modules.clear()
        self._module_slots.clear()
        self._module_states.clear()
        self._current_scene = 1
        # A user or another client may have navigated NUX Audio since the last
        # MCP call; never carry modal/page assumptions across apply requests.
        self._page = None
        completed = []
        for operation in plan.operations:
            try:
                completed.append(self._apply_one(operation))
            except Exception as error:  # noqa: BLE001 - driver boundary reports UI failures
                self._close_settings()
                return {
                    "ok": False,
                    "dry_run": False,
                    "operations": completed,
                    "failed_operation": operation.model_dump(),
                    "error": str(error),
                    "warnings": plan.warnings,
                }
        self._close_settings()
        return {"ok": True, "dry_run": False, "operations": completed, "warnings": plan.warnings}
