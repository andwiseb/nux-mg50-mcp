# Contributing

Contributions are welcome, especially verified screenshots/snapshots from different
NUX Audio and MG-50Li firmware versions.

## Setup

```bash
uv sync --extra dev
./scripts/build-bridge.sh
uv run pytest
```

Use `NUX_DRIVER=mock` for changes that do not require hardware.

## Hardware verification checklist

1. Back up important presets in NUX Audio.
2. Work on a disposable user preset and keep `save=false` until the result is checked.
3. Record the NUX Audio version and MG-50Li firmware version.
4. Run `nux-mg50 snapshot` before and after one isolated change.
5. Verify the device display/audio and read the value back from NUX Audio.
6. Test S1, S2 and S3 independently; scene state is easy to confuse with global state.
7. Include sanitized before/after snapshots and exact reproduction steps in the PR.

Rebuilding `native/NuxAudioBridge.swift` changes the local helper binary. macOS may ask
you to re-enable that exact helper in Privacy & Security → Accessibility. Screen
Recording is optional and is only needed to read the painted state of pre-existing
mute/bypass switches.

Do not commit proprietary NUX application binaries, firmware, commercial IR files,
personal presets, account tokens or cloud responses.

## Catalogue changes

`device_catalog.py` is descriptive. New firmware controls may be added after they are
visible in an official NUX Audio release or verified on hardware. Keep unknown controls
usable; do not turn the catalogue into a closed allow-list.
