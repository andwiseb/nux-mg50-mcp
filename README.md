# NUX MG-50Li MCP

Local, open-source MCP server that lets Claude, ChatGPT/Codex and other MCP clients
control a **NUX MG-50Li** through the **NUX Audio** macOS editor.

The server exposes one scene-aware tone document instead of making an agent perform
dozens of blind clicks. A request can contain the preset, S1/S2/S3, tempo, stomp
states, signal-chain routing, effect/amp/IR models, every named knob and device
settings. The server validates it, orders the changes, applies them, and can leave the
result in the live buffer or explicitly save it.

Firmware 1.1.1 preset volume is represented as `preset_volume_db` (−12 to +12 dB).
The Accessibility driver applies it only when the installed NUX Audio build exposes
the top-level dB readout and otherwise fails closed with a clear compatibility error.

> This project is independent and is not affiliated with or endorsed by NUX or
> Cherub Technology. NUX and MG-50Li are trademarks of their respective owners.

## Implementation status

- Preset selection and optional save
- Scene S1, S2 and S3
- Tempo/BPM, stomp states, and typed A/B/C stomp assignments
- Typed serial, split A/B + merge, and A-to-OUT/B-to-XLR routing plans
- NG, CMP, EFX, AMP, Image AMP, power amp, IR, EQ, S/R, DLY, RVB, WAH, MOD and P.L
- Model-specific knobs plus a forward-compatible arbitrary-control escape hatch
- One-message import of multilingual tone reports through `nux_apply_text`
- Input trim, global EQ, output/USB console, MIDI and other global settings
- Read-only dry-run plans, UI snapshots and diagnostics
- A deterministic mock driver for development without hardware

Preset selection, independent S1/S2/S3 chains, tempo, stomp assignments, model/knob
changes, all three routing layouts, and the global settings pages have been exercised
on a real MG-50Li with NUX Audio 1.1.7. The driver verifies each rebuilt chain slot
before continuing and fails closed whenever the requested visible control cannot be
found.

The macOS driver uses NUX Audio's Accessibility surface. A transport boundary is kept
separate so a verified direct USB-MIDI implementation can be added without changing
the MCP tools or tone JSON format. See [architecture](docs/ARCHITECTURE.md).

Long tone reports are supported at the MCP-client layer as well as short commands.
The report may be in any language or mix prose, headings, and tables. The client
semantically reduces the final applicable settings to a `ToneSpec`; the server then
validates and orders that device-only structure. Research notes, alternate guitars,
conditional troubleshooting values, and playing advice are not applied as controls.
This language-neutral split is intentional: the hardware server never relies on a
fixed list of translated words such as “on”, “scene”, or “gain”.

Before any UI mutation, known model names, parameter names, numeric ranges, and enum
values are checked against the bundled device catalogue. A bad extraction therefore
fails before the selected scene's chain is rebuilt. Unknown future firmware models
remain usable and produce an explicit forward-compatibility warning.

## Requirements

- macOS 13 or newer
- Python 3.11+
- Xcode Command Line Tools (`xcode-select --install`)
- NUX Audio installed
- MG-50Li connected to NUX Audio

## Install

With [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/andwiseb/nux-mg50-mcp.git
cd nux-mg50-mcp
uv sync --extra dev
./scripts/build-bridge.sh
uv run nux-mg50 doctor
```

Grant Accessibility access to the application that launches the MCP server and, if
macOS lists it separately, `.build/nux-audio-bridge` under:

`System Settings → Privacy & Security → Accessibility`

You can trigger the macOS prompt with:

```bash
uv run nux-mg50 request-access
```

Open NUX Audio, connect the MG-50Li, then repeat `doctor`. A ready installation reports
`"ready": true`.

Screen Recording is optional. It is used only to read the painted color of an existing
Console mute or pre-existing module bypass before deciding whether a click is needed.
Named module parameter switches use absolute drag positions, and applying a complete
tone with rebuilt chains does not require Screen Recording. On macOS 14+, grant it to
the launcher/helper if you want idempotent readback for existing mute/bypass states.

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

## Easiest use: paste a tone report

You do not need to write JSON. Paste a tone report into Claude, ChatGPT/Codex, or any
capable MCP client and add one sentence describing the destination and persistence:

> Apply this report to the currently selected preset and save it. Use the explicit
> final tables; ignore research notes, alternate guitars and conditional calibration
> suggestions.

The client calls `nux_apply_text` with the original document and its semantic
`ToneSpec` extraction. The server validates every known model, enum, control and range
before touching NUX Audio, then applies the operations in a safe order. A SHA-256
receipt identifies the exact source text used for the extraction.

Saving is controlled by a separate outer `save` flag. Text pasted from a report cannot
silently grant itself permission to overwrite a preset. If you say “do not save” or do
not mention persistence, the result stays in the live buffer. If you name no preset
slot, the server never invents one; an explicit save applies to the currently selected
slot.

The language understanding comes from the MCP host you are already talking to. The
local server needs no OpenAI/Anthropic API key and contains no fragile Turkish/English
keyword parser. This also lets it handle long mixed-language prose and tables while
the hardware layer remains deterministic and auditable.

## Example request

You can say:

> Select preset 43A. Make S1 a tight Brit 800 rhythm tone, S2 add more drive and
> delay, and S3 a louder lead. Set tempo to 112 BPM. Keep the preset unsaved.

The agent should call `nux_plan_tone` or `nux_apply_tone` with a structured `ToneSpec`.
A complete example is in [examples/complete-tone.json](examples/complete-tone.json).
An example distilled from a long-form tone report is in
[examples/beggin-17.json](examples/beggin-17.json).
Scene-local changes default to S1 when `scene` is omitted; pass `scene: 2` or `3`
explicitly for the other scenes.

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
| `nux_apply_text` | Validate and apply a semantic extraction from pasted prose/tables; records a source receipt |
| `nux_set_scene` | Select S1/S2/S3 |
| `nux_set_preset` | Select a preset and optionally save |
| `nux_set_tempo` | Set BPM |
| `nux_set_stomp` | Change a stomp-assigned block |
| `nux_assign_stomp` | Assign effect blocks to physical switch A, B or C |
| `nux_set_module` | Change one module/model/bypass/knob set |
| `nux_set_control` | Set a newly added or uncatalogued visible parameter |

## Safety behavior

- Changes are **not saved by default**. Set `save: true` explicitly.
- `dry_run: true` produces the exact ordered operation list without touching the UI.
- The server never writes guessed bytes to a preset or USB-MIDI endpoint.
- Chain replacement is destructive only in the selected live scene; preset storage is
  untouched until `save: true` is supplied.
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
The current device evidence and remaining checks are tracked in
[docs/HARDWARE-VERIFICATION.md](docs/HARDWARE-VERIFICATION.md).

## License

[MIT](LICENSE)
