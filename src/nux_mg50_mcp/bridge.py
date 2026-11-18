from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    selected: bool | None = None
    enabled: bool | None = None

    @property
    def text(self) -> str:
        return f"{self.title} {self.description} {self.value}".strip()


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
        timeout = 15.0
        if args and args[0] == "scroll-screen" and len(args) >= 5:
            # The native helper intentionally paces sustained wheel input so
            # Flutter and the pedal commit every step.
            timeout = max(timeout, float(args[4]) * 0.25 + 5.0)
        proc = subprocess.run(
            [str(self.executable), *(str(arg) for arg in args)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode:
            message = (
                proc.stderr.strip() or proc.stdout.strip() or f"bridge exited {proc.returncode}"
            )
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
        raw_probe = payload.get("nodes", payload if isinstance(payload, list) else [])
        # Flutter briefly exposes only the native window chrome when the app is
        # activated or a modal route is rebuilt. Retry instead of reporting every
        # control missing from that transient five-node tree.
        for _ in range(5):
            if len(raw_probe) > 5:
                break
            time.sleep(0.15)
            payload = self.run("snapshot")
            raw_probe = payload.get("nodes", payload if isinstance(payload, list) else [])
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
                selected=item.get("selected"),
                enabled=item.get("enabled"),
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
        containing = [
            node
            for node in candidates
            if any(needle and needle in _norm(node.text) for needle in needles)
        ]
        if containing:
            return min(containing, key=lambda node: len(_norm(node.text)))
        visible = sorted({node.text for node in candidates if node.text})[:40]
        raise ControlNotFound(f"control {wanted!r} not found; visible labels include: {visible}")

    def find_wait(
        self,
        labels: str | Iterable[str],
        *,
        roles: set[str] | None = None,
        timeout: float = 1.5,
    ) -> UINode:
        deadline = time.monotonic() + timeout
        last_error: ControlNotFound | None = None
        while time.monotonic() < deadline:
            try:
                return self.find(labels, roles=roles)
            except ControlNotFound as error:
                last_error = error
                time.sleep(0.1)
        assert last_error is not None
        raise last_error

    def click(self, labels: str | Iterable[str]) -> UINode:
        node = self.find(labels)
        # Flutter rebuilds its semantics tree asynchronously, so an element index
        # can become stale between the snapshot subprocess and the press subprocess.
        # Screen coordinates remain stable for the visible node.
        self.click_point(node.x + node.width / 2, node.y + node.height / 2)
        return node

    def click_wait(self, labels: str | Iterable[str], *, timeout: float = 1.5) -> UINode:
        node = self.find_wait(labels, timeout=timeout)
        self.click_point(node.x + node.width / 2, node.y + node.height / 2)
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

    def drag_points(self, source: tuple[float, float], target: tuple[float, float]) -> None:
        self.run("drag-screen", source[0], source[1], target[0], target[1])

    def right_click(self, node: UINode) -> None:
        self.run(
            "right-click-screen",
            node.x + node.width / 2,
            node.y + node.height / 2,
        )

    def click_point(self, x: float, y: float) -> None:
        self.run("click-screen", x, y)

    def sample_color(self, node: UINode) -> tuple[float, float, float]:
        sample = self.run("sample-screen", node.x, node.y, node.width, node.height)
        return float(sample["red"]), float(sample["green"]), float(sample["blue"])

    def window(self) -> UINode:
        windows = [node for node in self.nodes() if node.role == "AXWindow"]
        if not windows:
            raise ControlNotFound("NUX Audio window geometry not found")
        return windows[0]

    def escape(self) -> None:
        self.run("key", "escape")

    @staticmethod
    def _number(node: UINode) -> float | None:
        for raw in (node.value, node.title, node.description):
            match = re.search(r"[-+]?\d+(?:\.\d+)?", str(raw))
            if match:
                return float(match.group())
        return None

    def set_numeric_readout(self, readout: UINode, value: float) -> UINode:
        current = self._number(readout)
        if current is None:
            raise ControlNotFound("numeric readout has no numeric value")
        difference = float(value) - current
        if difference:
            fractional = any(
                abs(number - round(number)) > 1e-6 for number in (current, float(value))
            )
            step = 0.1 if fractional else 1.0
            count = abs(round(difference / step))
            self.scroll(readout, 1 if difference > 0 else -1, count)
        return readout

    def set_bounded_numeric_readout(
        self,
        readout: UINode,
        value: float,
        *,
        minimum: float,
        maximum: float,
        step: float = 1.0,
    ) -> UINode:
        """Set a painted control without trusting its potentially stale AXValue.

        NUX Audio's tempo field keeps an old semantic value after tap/scroll changes.
        Saturating at the known lower bound and walking to the target is slower than a
        delta, but it produces an absolute device value even after arbitrary UI state.
        """
        target = float(value)
        if not minimum <= target <= maximum:
            raise ValueError(f"value must be between {minimum} and {maximum}")
        # Do not overshoot the lower bound. Flutter can leave saturated wheel
        # events queued; immediately reversing direction then drops most of the
        # upward steps and produces a value close to the minimum.
        span = round((maximum - minimum) / step)
        self.scroll(readout, -1, span)
        # Let the editor/device finish consuming the downward burst before the
        # direction change. This is part of the commit protocol, not cosmetic.
        time.sleep(1.0)
        offset = round((target - minimum) / step)
        if offset:
            self.scroll(readout, 1, offset)
        return readout

    def set_parameter(self, parameter: str, value: object) -> UINode:
        """Set a model parameter using the editor's ordered control strip.

        NUX Audio exposes parameter labels as one multiline AX group and each numeric
        readout as a child. The knob itself is custom-painted; scrolling its readout is
        the editor-supported one-step adjustment gesture.
        """
        needle = _norm(parameter)
        nodes: list[UINode] = []
        strips: list[tuple[UINode, list[str]]] = []
        for attempt in range(6):
            nodes = self.nodes()
            strips = []
            for node in nodes:
                source = max(
                    (node.title, node.description, node.value), key=lambda text: text.count("\n")
                )
                lines = [line.strip() for line in source.splitlines() if line.strip()]
                if len(lines) > 1 and any(_norm(line) == needle for line in lines):
                    strips.append((node, lines))
            if strips:
                break
            if attempt < 5:
                time.sleep(0.12)
        if not strips:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                raise ControlNotFound(f"numeric parameter strip for {parameter!r} is not visible")
            # Native text fields/sliders and forward-compatible enum controls.
            return self.set_value(parameter, value)
        strip, labels = max(strips, key=lambda item: len(item[1]))
        slot = next(index for index, label in enumerate(labels) if _norm(label) == needle)
        # Flutter lays these custom controls out with roughly 1.5 slot-width margins.
        # The actual numeric AX readouts below are used to absorb scaling differences.
        expected_x = strip.x + strip.width * (slot + 1.5) / (len(labels) + 2)
        numeric = [
            node
            for node in nodes
            if node.index != strip.index
            and self._number(node) is not None
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
            # numeric readout. Module boolean switches are vertical: dragging toward
            # the requested pole makes the operation idempotent, unlike a blind click.
            center_y = strip.y + strip.height / 2
            if isinstance(value, bool):
                self.drag_points(
                    (expected_x, center_y),
                    (expected_x, center_y + (-15 if value else 15)),
                )
                return strip
            self.run("click-screen", expected_x, center_y)
            return self.click(str(value))
        if readout_for_grid is None:
            raise ControlNotFound(f"numeric readout for parameter {parameter!r} not found")
        readout = readout_for_grid
        return self.set_numeric_readout(readout, value)

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
            node
            for node in nodes
            if node.role == "AXButton"
            and not node.text
            and node.y < window.y + 150
            and node.x > window.x + window.width * 0.8
        ]
        if not candidates:
            raise ControlNotFound("NUX Audio More menu button not found")
        button = max(candidates, key=lambda node: node.x)
        self.click_point(button.x + button.width / 2, button.y + button.height / 2)
        return button
