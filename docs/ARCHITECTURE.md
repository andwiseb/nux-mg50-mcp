# Architecture

```text
Claude / ChatGPT / Codex
          │ semantic extraction
          ├── pasted prose/tables + ToneSpec ── nux_apply_text
          └── ToneSpec directly ─────────────── nux_apply_tone
          │ MCP stdio
          ▼
 Validator + planner ───── dry-run / mock driver
          │ ordered operations
          ▼
     Driver boundary
          │
          ├── NUX Audio Accessibility driver (implemented)
          └── direct USB-MIDI driver (reserved; only after hardware verification)
```

## Why the boundary exists

The MG-50Li editor protocol is not treated as public or stable. Sending speculative
SysEx or editing undocumented preset offsets can corrupt user data. The current driver
uses the official NUX Audio editor as the protocol authority and controls its semantic
macOS Accessibility tree. `native/NuxAudioBridge.swift` is the only privileged native
component.

`ToneSpec` is transport-neutral. It represents preset, scenes, routing, modules, stomp,
tempo and settings. The planner converts it into deterministic operations in this order:

1. select preset and scene;
2. select routing and rebuild the active scene's chain when requested;
3. select a chain module/model, then set bypass/switches and knobs;
4. rebuild the base layout independently in each explicit non-base scene and apply its overrides;
5. apply stomp assignments and global settings;
6. rename/save only when requested.

Natural-language interpretation deliberately stays in the MCP host. Claude/ChatGPT
already has the multilingual semantic context needed to distinguish final tables from
research notes and conditional alternatives. `nux_apply_text` receives both the exact
source and that structured extraction, validates the extraction locally, and returns a
SHA-256 source receipt. This avoids a second cloud API key and avoids pretending that a
fixed regex/keyword parser can understand arbitrary tone reports. Its outer `save`
argument overrides any embedded `spec.save` value, so pasted content cannot authorize
persistence by itself.

NUX Audio stores the signal chain independently in S1, S2 and S3. The planner therefore
copies a top-level routing layout and module baseline into every explicitly requested
non-base scene unless that scene provides its own routing. The driver clears at most
once per scene per apply transaction, so split branch A and B are rebuilt together.

The native helper uses semantic Accessibility nodes where NUX Audio publishes them.
For custom-painted Flutter controls it uses calibrated coordinates relative to the
editor window, followed by semantic/readout verification. It never sends undocumented
USB or preset bytes.

## Direct MIDI roadmap

A direct driver should not be merged from assumptions based on other NUX products.
It needs captured MG-50Li USB-MIDI request/response pairs, firmware/version negotiation,
read-back verification, timeouts and golden packet tests. It must implement the same
`Driver` interface, leaving every MCP tool and tone file unchanged.
