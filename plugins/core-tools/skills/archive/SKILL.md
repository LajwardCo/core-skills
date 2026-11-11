---
name: archive
description: Archive a Claude Code terminal chat (hide it from `claude --resume` without deleting it), list archived chats, or restore one. Use for /archive, "archive this chat", "list archived chats", "restore chat X".
---
Silent skill: run the command, then output nothing (no recap, no tips). Speak only to ask a needed
confirmation or report a failure in one line.

`S=<skill>/scripts/archive.py` (absolute path from this skill's base directory). It works on the
account of the current chat (`$CLAUDE_CONFIG_DIR`, default `~/.claude`). Transcripts are moved to
`<config>/archived-sessions/`, never deleted.

| Ask | Run (one Bash call) |
|---|---|
| archive this chat | `python3 $S this` — moved once this chat's process exits |
| archive another (closed) chat `<id>` | `python3 $S id <id-or-prefix>` |
| list archived | `python3 $S list` — show output |
| restore `<id>` | `python3 $S restore <id-prefix>` |
| undo "archive this chat" before it is moved | `python3 $S cancel` |

Confirm first only if the id matches several chats, or the target chat is open in another window.
Desktop-app chat (`CLAUDE_CODE_ENTRYPOINT` != `cli`): archive from the app's sidebar instead; say so in one line.
Never delete transcripts.
