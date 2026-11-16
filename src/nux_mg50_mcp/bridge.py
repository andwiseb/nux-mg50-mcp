from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .errors import BridgeError, ControlNotFound


@dataclass(frozen=True)
class UINode:
    index: int
    role: str
    title: str
    description: str
    value: str
    x: float
    y: float
    width: float
    height: float

    @property
    def text(self) -> str:
        return " ".join((self.title, self.description, self.value)).strip()


def _norm(value: object) -> str:
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


class AccessibilityBridge:
    """Thin subprocess wrapper around the auditable native macOS helper."""

    def __init__(self, executable: str | Path | None = None) -> None:
        configured = executable or os.environ.get("NUX_BRIDGE")
        root = Path(__file__).resolve().parents[2]
        self.executable = Path(configured) if configured else root / ".build" / "nux-audio-bridge"

    def run(self, *args: object) -> Any:
        if not self.executable.exists():
            raise BridgeError("native bridge is missing; run scripts/build-bridge.sh")
        proc = subprocess.run(
            [str(self.executable), *(str(arg) for arg in args)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode:
            message = proc.stderr.strip() or proc.stdout.strip() or f"bridge exited {proc.returncode}"
            raise BridgeError(message)
        output = proc.stdout.strip()
        if not output:
            return {"ok": True}
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"ok": True, "message": output}

    def doctor(self) -> dict[str, Any]:
        return self.run("doctor")

    def activate(self) -> dict[str, Any]:
        return self.run("activate")

    def request_access(self) -> dict[str, Any]:
        return self.run("request-access")

    def nodes(self) -> list[UINode]:
        payload = self.run("snapshot")
        raw_nodes = payload.get("nodes", payload if isinstance(payload, list) else [])
        return [
            UINode(
                index=int(item.get("index", index)),
                role=str(item.get("role", "")),
                title=str(item.get("title", "")),
                description=str(item.get("description", "")),
                value=str(item.get("value", "")),
                x=float(item.get("x", 0)),
                y=float(item.get("y", 0)),
                width=float(item.get("width", 0)),
                height=float(item.get("height", 0)),
            )
            for index, item in enumerate(raw_nodes)
        ]

    def find(self, labels: str | Iterable[str], *, roles: set[str] | None = None) -> UINode:
        wanted = [labels] if isinstance(labels, str) else list(labels)
        needles = [_norm(label) for label in wanted]
        candidates = [node for node in self.nodes() if not roles or node.role in roles]
        exact = [node for node in candidates if _norm(node.text) in needles]
        if exact:
            return exact[0]
        containing = [node for node in candidates if any(needle and needle in _norm(node.text) for needle in needles)]
        if containing:
            return min(containing, key=lambda node: len(_norm(node.text)))
        visible = sorted({node.text for node in candidates if node.text})[:40]
        raise ControlNotFound(f"control {wanted!r} not found; visible labels include: {visible}")

    def click(self, labels: str | Iterable[str]) -> UINode:
        node = self.find(labels)
        self.run("press-snapshot", node.index)
        return node

    def set_value(self, labels: str | Iterable[str], value: object) -> UINode:
        node = self.find(labels)
        self.run("set-snapshot", node.index, value)
        return node

    def scroll(self, node: UINode, direction: int, count: int) -> None:
        x = node.x + node.width / 2
        y = node.y + node.height / 2
        remaining = count
        while remaining:
            batch = min(remaining, 100)
            self.run("scroll-screen", x, y, direction, batch)
            remaining -= batch

    def drag(self, source: UINode, target: UINode) -> None:
        self.run(
            "drag-screen",
            source.x + source.width / 2,
            source.y + source.height / 2,
            target.x + target.width / 2,
            target.y + target.height / 2,
        )

    def escape(self) -> None:
        self.run("key", "escape")

    @staticmethod
    def _number(node: UINode) -> float | None:
        for raw in (node.value, node.title, node.description):
            match = re.search(r"[-+]?\d+(?:\.\d+)?", str(raw))
            if match:
                return float(match.group())
        return None

    def set_parameter(self, parameter: str, value: object) -> UINode:
        """Set a model parameter using the editor's ordered control strip.

        NUX Audio exposes parameter labels as one multiline AX group and each numeric
        readout as a child. The knob itself is custom-painted; scrolling its readout is
        the editor-supported one-step adjustment gesture.
        """
        nodes = self.nodes()
        needle = _norm(parameter)
        strips: list[tuple[UINode, list[str]]] = []
        for node in nodes:
            source = max((node.title, node.description, node.value), key=lambda text: text.count("\n"))
            lines = [line.strip() for line in source.splitlines() if line.strip()]
            if len(lines) > 1 and any(_norm(line) == needle for line in lines):
                strips.append((node, lines))
        if not strips:
            # Native text fields/sliders and forward-compatible controls.
            return self.set_value(parameter, value)
        strip, labels = max(strips, key=lambda item: len(item[1]))
        slot = next(index for index, label in enumerate(labels) if _norm(label) == needle)
        # Flutter lays these custom controls out with roughly 1.5 slot-width margins.
        # The actual numeric AX readouts below are used to absorb scaling differences.
        expected_x = strip.x + strip.width * (slot + 1.5) / (len(labels) + 2)
        numeric = [
            node for node in nodes
            if node.index != strip.index and self._number(node) is not None
            and strip.x <= node.x + node.width / 2 <= strip.x + strip.width
            and strip.y <= node.y + node.height / 2 <= strip.y + strip.height
        ]
        if labels[0].rstrip().endswith(":") and len(numeric) == len(labels) - 1:
            numeric.sort(key=lambda node: (node.y, node.x))
            readout_for_grid = numeric[slot - 1] if slot > 0 else None
        else:
            numeric.sort(key=lambda node: abs((node.x + node.width / 2) - expected_x))
            readout_for_grid = numeric[0] if numeric else None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            # Switches and enumerations occupy the same evenly-spaced slots but have no
            # numeric readout. Click the slot, then choose an enum option when supplied.
            self.run("click-screen", expected_x, strip.y + strip.height / 2)
            if not isinstance(value, bool):
                return self.click(str(value))
            return strip
        if readout_for_grid is None:
            raise ControlNotFound(f"numeric readout for parameter {parameter!r} not found")
        readout = readout_for_grid
        current = self._number(readout)
        assert current is not None
        difference = float(value) - current
        if difference:
            fractional = any(abs(number - round(number)) > 1e-6 for number in (current, float(value)))
            step = 0.1 if fractional else 1.0
            count = abs(int(round(difference / step)))
            self.scroll(readout, 1 if difference > 0 else -1, count)
        return readout

    def snapshot(self) -> dict[str, Any]:
        nodes = self.nodes()
        return {
            "count": len(nodes),
            "nodes": [node.__dict__ | {"text": node.text} for node in nodes],
        }

    def open_more_menu(self) -> UINode:
        nodes = self.nodes()
        windows = [node for node in nodes if node.role == "AXWindow"]
        if not windows:
            raise ControlNotFound("NUX Audio window geometry not found")
        window = windows[0]
        candidates = [
            node for node in nodes
            if node.role == "AXButton" and not node.text
            and node.y < window.y + 150 and node.x > window.x + window.width * 0.8
        ]
        if not candidates:
            raise ControlNotFound("NUX Audio More menu button not found")
        button = max(candidates, key=lambda node: node.x)
        self.run("press-snapshot", button.index)
        return button
