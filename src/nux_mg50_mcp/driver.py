from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import Any

from .bridge import AccessibilityBridge
from .models import ApplyPlan, Operation
from .errors import BridgeError


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

    LABELS = {
        "scene": ("Scene", "SCENE"),
        "tempo": ("Tempo", "TAP", "BPM"),
        "preset": ("Preset", "PRESET"),
        "preset_name": ("Preset name",),
        "save": ("Save Preset", "Save", "SAVE"),
    }

    def __init__(self, bridge: AccessibilityBridge | None = None) -> None:
        self.bridge = bridge or AccessibilityBridge()
        self._page: str | None = None

    def _open_page(self, name: str) -> None:
        if self._page == name:
            return
        self.bridge.open_more_menu()
        self.bridge.click(name)
        self._page = name

    def _open_settings_page(self, page: str) -> None:
        settings_pages = {
            "Settings", "Input Trim", "Output Mode", "Global Eq", "Display",
            "Brightness", "Para.Follow", "Console", "MIDI Setting", "Other",
        }
        if self._page not in settings_pages:
            self._open_page("Settings")
        if self._page != page:
            self.bridge.click((page, page.replace(" ", "")))
            self._page = page

    def status(self) -> dict[str, Any]:
        result = self.bridge.doctor()
        result["driver"] = "nux-audio-accessibility"
        result["ready"] = bool(result.get("appRunning") and result.get("accessibilityTrusted"))
        return result

    def snapshot(self) -> dict[str, Any]:
        return self.bridge.snapshot()

    def _apply_one(self, operation: Operation) -> dict[str, Any]:
        control = operation.control
        if operation.action == "save":
            self.bridge.open_more_menu()
            node = self.bridge.click(self.LABELS["save"])
        elif control == "scene":
            node = self.bridge.click((f"S{operation.value}", f"Scene {operation.value}"))
        elif control == "preset":
            nodes = self.bridge.nodes()
            current = next((item for item in nodes if re.fullmatch(r"\d{1,2}[ABC]", item.text.strip())), None)
            node = current or self.bridge.find(self.LABELS["preset"])
            self.bridge.run("press-snapshot", node.index)
            node = self.bridge.click(str(operation.value))
            self.bridge.click("OK")
        elif control == "preset_name":
            node = self.bridge.set_value(self.LABELS["preset_name"], operation.value)
        elif control == "tempo":
            node = self.bridge.set_value(self.LABELS["tempo"], operation.value)
        elif control == "module":
            node = self.bridge.click((str(operation.value), str(operation.value).upper()))
            self._page = "home"
        elif control.startswith("settings."):
            _, group, parameter = control.split(".", 2)
            pages = {
                "input_trim": "Input Trim",
                "global_eq": "Global EQ",
                "output_console": "Console",
                "midi": "MIDI Setting",
                "other": "Other",
            }
            page = pages[group]
            self._open_settings_page(page)
            node = self.bridge.set_parameter(parameter, operation.value)
        elif operation.action == "assign":
            switch = control.rsplit(".", 1)[-1]
            self._open_page("Stomp")
            modules = list(operation.value)
            # The Stomp editor exposes every block followed by A/B/C/UNASSIGN.
            # Selecting a block then its destination is deterministic and mirrors
            # the editor's own assignment workflow.
            if not modules:
                self.bridge.click(switch)
                node = self.bridge.click("UNASSIGN")
            else:
                node = None
                for module in modules:
                    self.bridge.click(str(module))
                    node = self.bridge.click(switch)
                assert node is not None
        elif operation.action == "arrange":
            raise BridgeError(
                f"{control} requires calibrated drag-and-drop support; "
                "the operation was not applied"
            )
        elif operation.action == "select":
            # Open a selector (model/routing), then choose the requested visible option.
            if control.endswith(".model"):
                nodes = self.bridge.nodes()
                label = self.bridge.find("Model")
                candidates = [item for item in nodes if item.index < label.index and item.role.endswith("Image") and item.text]
                opener = max(candidates, key=lambda item: item.index) if candidates else label
                self.bridge.run("press-snapshot", opener.index)
            else:
                self.bridge.click((control, control.split(".")[-1], control.replace(".", " ")))
            node = self.bridge.click(str(operation.value))
        elif operation.action == "toggle":
            labels = (control, control.split(".")[-1], control.replace(".", " "))
            node = self.bridge.find(labels)
            current = node.value.casefold().strip()
            desired = bool(operation.value)
            known_true = current in {"1", "true", "on", "yes", "checked", "enabled"}
            known_false = current in {"0", "false", "off", "no", "unchecked", "disabled"}
            if not ((desired and known_true) or (not desired and known_false)):
                self.bridge.run("press-snapshot", node.index)
        else:
            # The last component is normally the exact visible knob/switch label.
            labels = (control, control.split(".")[-1], control.replace(".", " "))
            if operation.action == "click":
                node = self.bridge.click(labels)
            else:
                node = self.bridge.set_parameter(control.split(".")[-1], operation.value)
        return {"operation": operation.model_dump(), "node": node.__dict__}

    def apply(self, plan: ApplyPlan, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {"ok": True, "dry_run": True, "operations": [op.model_dump() for op in plan.operations], "warnings": plan.warnings}
        unsupported = [
            op for op in plan.operations
            if op.action == "arrange" or op.control.startswith("routing.")
        ]
        if unsupported:
            return {
                "ok": False,
                "dry_run": False,
                "operations": [],
                "warnings": plan.warnings,
                "error": "Signal-chain routing is not calibrated for this editor build.",
                "unsupported": [op.model_dump() for op in unsupported],
            }
        status = self.status()
        if not status["ready"]:
            return {"ok": False, "status": status, "operations": [], "warnings": plan.warnings}
        self.bridge.activate()
        completed = []
        for operation in plan.operations:
            try:
                completed.append(self._apply_one(operation))
            except Exception as error:
                return {
                    "ok": False,
                    "dry_run": False,
                    "operations": completed,
                    "failed_operation": operation.model_dump(),
                    "error": str(error),
                    "warnings": plan.warnings,
                }
        return {"ok": True, "dry_run": False, "operations": completed, "warnings": plan.warnings}
