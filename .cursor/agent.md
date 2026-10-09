# Aegis Agent Workspace

This project uses Aegis Agent Workspace for multi-agent coordination. Follow these rules every session.

## Workspace loop

- **On session start:** call `workspace_get_context` (cold start: brief, roster, recent messages, open pointers).
- **Every turn, before ending your response:** call `workspace_check_mentions` (cheap poll, ids only).
- **If new mention ids are returned:** call `workspace_get_context` or `workspace_get_messages` for the body, then `workspace_post` to acknowledge/reply. Use `@handle` in content to mention others; your own handle is auto-excluded.
- **Before marking work done:** call `workspace_update_pointer` with status one of `pending`, `review`, `done`.
- **Never ask the user whether to check the workspace** — always do it silently.
