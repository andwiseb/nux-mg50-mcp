# NUX MG-50Li MCP

Local, open-source MCP server that lets Claude, ChatGPT/Codex and other MCP clients
control a **NUX MG-50Li** through the **NUX Audio** macOS editor.

The server exposes one scene-aware tone document instead of making an agent perform
dozens of blind clicks. A request can contain the preset, S1/S2/S3, tempo, stomp
states, signal-chain routing, effect/amp/IR models, every named knob and device
settings. The server validates it, orders the changes, applies them, and can leave the
result in the live buffer or explicitly save it.

> This project is independent and is not affiliated with or endorsed by NUX or
> Cherub Technology. NUX and MG-50Li are trademarks of their respective owners.

## Implementation status

- Preset selection and optional save
- Scene S1, S2 and S3
- Tempo/BPM, stomp states, and typed A/B/C stomp assignments
- Typed serial, split A/B + merge, and A-to-OUT/B-to-XLR routing plans
- NG, CMP, EFX, AMP, Image AMP, power amp, IR, EQ, S/R, DLY, RVB, WAH, MOD and P.L
- Model-specific knobs plus a forward-compatible arbitrary-control escape hatch
- Input trim, global EQ, output/USB console, MIDI and other global settings
- Read-only dry-run plans, UI snapshots and diagnostics
- A deterministic mock driver for development without hardware

Preset selection, scene switching and numeric knob gestures have been exercised on a
real MG-50Li with NUX Audio 1.1.7. The full routing vocabulary is validated and shown
in dry-runs, but live chain reordering is deliberately rejected before any mutation
until drag/drop calibration for the installed editor build is complete. This prevents
the server from claiming success after a blind chain move. The same fail-closed rule
applies whenever a visible control cannot be found.

The macOS driver uses NUX Audio's Accessibility surface. A transport boundary is kept
separate so a verified direct USB-MIDI implementation can be added without changing
the MCP tools or tone JSON format. See [architecture](docs/ARCHITECTURE.md).

## Requirements

- macOS 13 or newer
- Python 3.11+
- Xcode Command Line Tools (`xcode-select --install`)
- NUX Audio installed
- MG-50Li connected to NUX Audio

## Install

With [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/YOUR_NAME/nux-mg50-mcp.git
cd nux-mg50-mcp
uv sync --extra dev
./scripts/build-bridge.sh
uv run nux-mg50 doctor
```

Grant Accessibility access to the application that launches the MCP server (for
example Terminal, Claude Desktop or Codex) under:

`System Settings → Privacy & Security → Accessibility`

You can trigger the macOS prompt with:

```bash
uv run nux-mg50 request-access
```

Open NUX Audio, connect the MG-50Li, then repeat `doctor`. A ready installation reports
`"ready": true`.

## MCP client configuration

Use the absolute checkout path. Claude Desktop and other stdio MCP clients accept a
configuration equivalent to:

```json
{
  "mcpServers": {
    "nux-mg50": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/nux-mg50-mcp",
        "run",
        "nux-mg50-mcp"
      ]
    }
  }
}
```

Restart the client after changing its configuration. The client process itself needs
Accessibility permission because it launches the native helper.

## Example request

You can say:

> Select preset 43A. Make S1 a tight Brit 800 rhythm tone, S2 add more drive and
> delay, and S3 a louder lead. Set tempo to 112 BPM. Keep the preset unsaved.

The agent should call `nux_plan_tone` or `nux_apply_tone` with a structured `ToneSpec`.
A complete example is in [examples/complete-tone.json](examples/complete-tone.json).

CLI dry-run:

```bash
uv run nux-mg50 validate examples/complete-tone.json
uv run nux-mg50 apply --dry-run examples/complete-tone.json
```

## MCP tools

| Tool | Purpose |
|---|---|
| `nux_doctor` | Check NUX Audio and permissions |
| `nux_snapshot` | Read visible controls/values for discovery and verification |
| `nux_capabilities` | Describe models, parameters, ranges, routing and settings |
| `nux_plan_tone` | Validate and order a complete tone without changing anything |
| `nux_apply_tone` | Apply the full `ToneSpec` surface |
| `nux_set_scene` | Select S1/S2/S3 |
| `nux_set_preset` | Select a preset and optionally save |
| `nux_set_tempo` | Set BPM |
| `nux_set_stomp` | Change a stomp-assigned block |
| `nux_assign_stomp` | Assign effect blocks to physical switch A, B or C |
| `nux_set_module` | Change one module/model/bypass/knob set |
| `nux_set_control` | Set a newly added or uncatalogued visible control |

## Safety behavior

- Changes are **not saved by default**. Set `save: true` explicitly.
- `dry_run: true` produces the exact ordered operation list without touching the UI.
- The server never writes guessed bytes to a preset or USB-MIDI endpoint.
- Unknown firmware controls remain available through `nux_snapshot` and
  `nux_set_control`; the catalogue is guidance, not a version lock.

## Development

```bash
uv run pytest
NUX_DRIVER=mock uv run nux-mg50-mcp
```

The native helper is intentionally small and auditable. Build it after editing:

```bash
./scripts/build-bridge.sh
```

Hardware/UI verification instructions are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
