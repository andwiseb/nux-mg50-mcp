# Security policy

Report a vulnerability privately through GitHub Security Advisories when the repository
is published. Do not open a public issue for a vulnerability that could execute commands,
expose local files, or overwrite device data.

The server is intended for local stdio use. Do not expose it over a network transport
without authentication and operating-system isolation. Only install MCP configurations
from repositories you trust: the native helper receives macOS Accessibility privileges.
