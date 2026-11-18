# MG-50Li device surface

The bundled catalogue covers:

- routing: two-row serial, split parallel A/B + merge, split A→OUT/B→XLR;
- S1/S2/S3, preset/name, firmware-supported ±12 dB preset volume, tempo and stomp assignments;
- NG, CMP, drive/boost/distortion/fuzz/octave, AMP and Image AMP, power amp;
- mono/stereo IR, microphone/position/distance, cuts, level and pan;
- 6-band, Align and 10-band EQ;
- delay, reverb, send/return, wah, modulation and pedal level;
- input trims and output mode;
- global EQ (enable, HPF, bands, level, LPF and LPF enable);
- home/boot display, display and footswitch brightness, parameter-follow behavior;
- phones/output/XLR levels, input monitor, USB mode, dry input and loopback;
- MIDI channel/in/out/program-change range;
- S3 behavior, tap scope, phones routing, patch rolling/tail and language.

Each explicit scene may define its own `routing`, `modules`, `tempo_bpm`, and stomp
states. A top-level routing/modules baseline is copied to explicit non-base scenes so
the same request can describe a complete three-scene preset without relying on prior
device state.

Call `nux_capabilities()` for the machine-readable catalogue and
`nux_capabilities("AMP")` for a single section. The high-level schema intentionally
accepts additional model and parameter names so NUX Audio updates do not make the MCP
server unusable.
