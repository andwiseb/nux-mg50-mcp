#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$ROOT/.build"
xcrun swiftc -O -module-cache-path "$ROOT/.build/module-cache" \
  "$ROOT/native/NuxAudioBridge.swift" -o "$ROOT/.build/nux-audio-bridge"
echo "Built $ROOT/.build/nux-audio-bridge"
