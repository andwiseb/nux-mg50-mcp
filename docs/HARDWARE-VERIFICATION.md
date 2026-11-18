# Hardware verification

This matrix records checks performed against a physical MG-50Li through NUX Audio
1.1.7 on macOS. Tests use disposable user preset 97A and leave `save=false` unless a
row explicitly tests persistence. The firmware version still needs to be recorded.

| Surface | Evidence | Status |
|---|---|---|
| Preset selector | Selected 97A atomically through the Flutter modal | Verified |
| Preset volume ±12 dB | Public schema and readout driver are implemented for firmware/editor builds that expose the top-level dB value; the connected editor does not currently publish it | Firmware-gated |
| Tempo | Painted readout clamps at 40/240; MCP set 123 exactly and restored 120. Sustained wheel events re-enter the hit-test point; stale AXValue was rejected as false evidence | Verified |
| Serial chain | Built and verified all 13 module categories across both rows | Verified |
| Stomp assignment | GATE1→A, AMP1→B, DLY1→A, C empty, visually inspected | Verified |
| Module model and numeric knob | Noise Gate and Brit 800 model/knob smoke | Verified |
| Global settings | 31 operations across all settings pages, visually inspected | Verified |
| S1/S2/S3 independent complete chains | Built NG→AMP→DLY independently in all three scenes; S2 GAIN=32 and S3 retry path visually inspected | Verified |
| Parallel split + merge | NG→AMP on A, DLY→RVB on B, merge layout, CHAIN A/B and levels 33/67 visually inspected | Verified |
| Split A→OUT / B→XLR | CMP→EFX on A/OUT and MOD→PL on B/XLR, top selector position and levels 41/59 visually inspected | Verified |
| Preset rename and save | Renamed 97A to MCP PROOF, saved, switched to 97B and back, verified persistence; restored and persisted USER'S EMPTY | Verified |
| Module boolean switch | Jazz Clean BRIGHT dragged off twice idempotently, then restored on | Verified |
| Console mute readback | All five AX buttons resolved; ScreenCaptureKit reached TCC and macOS denied optional Screen Recording permission. No blind toggle was performed | Permission-gated |

Every non-permission/firmware-gated row has an observed NUX Audio/device result. A successful
dry-run, return code, semantic AXValue, or coordinate click alone is not accepted as
hardware evidence. Console mute remains usable after granting the optional Screen
Recording permission documented in the README; refusing that permission deliberately
fails safely instead of toggling an unknown state.
