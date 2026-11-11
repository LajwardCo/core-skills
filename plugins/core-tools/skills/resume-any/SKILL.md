---
name: resume-any
description: List and resume ANY Claude Code chat of this account across ALL projects, from inside a running chat. Built-in /resume only shows the current folder. Use for /resume-any, "show all my chats", "resume a chat from another project", "resume chat about X".
---

Silent skill: show the table, nothing else. No recap, no tips.

`S=<skill>/scripts/claude-resume-any.py` (absolute path from this skill's base directory; it reads
`$CLAUDE_CONFIG_DIR`, so it lists the account this chat belongs to). macOS + tmux or Terminal.app.

| Ask | Run |
|---|---|
| `/resume-any` | `python3 -I $S list` — print output verbatim, then ask: `pick #` |
| `/resume-any 60` | `python3 -I $S list 60` |
| `/resume-any <words>` | `python3 -I $S list 30 <words>` (filters title / project / branch) |
| user answers with a number | `python3 -I $S go <n>` |

`go <n>` replaces THIS window with the picked chat: waits for the turn to finish, sends `/exit`,
then `cd <project> && claude --resume <id>` in the same tmux pane (send-keys) or the same
Terminal.app tab (AppleScript). In other terminals it prints the command to run yourself.

Rules:
- Before `go`, say in one line which chat is being opened; it closes the current one.
- `*` in the list marks this chat — `go` on it is refused.
- After `go` succeeds: say nothing more, the window is about to be taken over.
- Chats whose project folder no longer exists are hidden. Log: `~/.cache/resume-any/resume-any.log`.
