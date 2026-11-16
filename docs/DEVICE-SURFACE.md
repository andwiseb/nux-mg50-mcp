# MG-50Li device surface

The bundled catalogue covers:

- routing: two-row serial, split parallel A/B + merge, split A→OUT/B→XLR;
- S1/S2/S3, preset, tempo and stomp assignments;
- NG, CMP, drive/boost/distortion/fuzz/octave, AMP and Image AMP, power amp;
- mono/stereo IR, microphone/position/distance, cuts, level and pan;
- 6-band, Align and 10-band EQ;
- delay, reverb, send/return, wah, modulation and pedal level;
- input trims, global EQ, output/USB routing, MIDI and patch behavior.

Call `nux_capabilities()` for the machine-readable catalogue and
`nux_capabilities("AMP")` for a single section. The high-level schema intentionally
accepts additional model and parameter names so NUX Audio updates do not make the MCP
server unusable.
