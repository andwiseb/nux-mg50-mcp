# Architecture

```text
Claude / ChatGPT / Codex
          │ MCP stdio
          ▼
   Typed MCP tools
          │ ToneSpec
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
2. select a chain module and model;
3. set bypass/switches and knobs;
4. repeat for explicit S1/S2/S3 overrides;
5. apply routing and global settings (live routing fails closed until the editor build is calibrated);
6. save only when requested.

## Direct MIDI roadmap

A direct driver should not be merged from assumptions based on other NUX products.
It needs captured MG-50Li USB-MIDI request/response pairs, firmware/version negotiation,
read-back verification, timeouts and golden packet tests. It must implement the same
`Driver` interface, leaving every MCP tool and tone file unchanged.
