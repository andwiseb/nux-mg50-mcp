from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bridge import AccessibilityBridge
from .driver import NuxAudioDriver
from .models import ToneSpec
from .planner import plan_tone


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="nux-mg50", description="NUX MG-50Li macOS control and diagnostics"
    )
    subs = result.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor", help="check NUX Audio and Accessibility permission")
    subs.add_parser("request-access", help="open the macOS Accessibility permission prompt")
    subs.add_parser("snapshot", help="dump visible NUX Audio semantics as JSON")
    apply = subs.add_parser("apply", help="apply a ToneSpec JSON file")
    apply.add_argument("file", type=Path)
    apply.add_argument("--dry-run", action="store_true")
    validate = subs.add_parser("validate", help="validate and plan a ToneSpec JSON file")
    validate.add_argument("file", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    bridge = AccessibilityBridge()
    driver = NuxAudioDriver(bridge)
    if args.command == "doctor":
        output = driver.status()
    elif args.command == "request-access":
        output = bridge.request_access()
    elif args.command == "snapshot":
        output = driver.snapshot()
    else:
        spec = ToneSpec.model_validate_json(args.file.read_text(encoding="utf-8"))
        plan = plan_tone(spec)
        output = (
            plan.model_dump()
            if args.command == "validate"
            else driver.apply(plan, dry_run=args.dry_run)
        )
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
