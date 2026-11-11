---
name: mac-guard
description: Check whether this Mac has the headroom to start another Claude session, and whether Docker should be closed. Use before opening a new chat/agent, after finishing a task, or when the machine lags, beachballs, overheats or kernel-panics. Trigger - /mac-guard, "can I start another chat", "is my mac ok", "why is it lagging".
---

# mac-guard

Running several AI coding sessions at once on one Mac ends the same way every time:
agents + their dev servers + Docker fill RAM, swap fills, the kernel spends its time
paging, `watchdogd` misses 90 s of check-ins, kernel panic
(`panic(...): watchdog timeout: no checkins from watchdogd in 90 seconds`).
Nothing to debug when it happens - just check headroom before you add load.

## Do this

Run it and print the one line it outputs, verbatim, including the escape codes. Stop there.

```bash
<skill>/scripts/check.sh   # absolute path from this skill's base directory
```

One dim-grey line: swap used, live chat count, verdict
(`ok to start` / `free something first` / `don't start another`), and what to close first.
Add nothing - no table, no analysis, no second measurement. This skill must stay cheap.

## Thresholds

Scaled from installed RAM, so the same script fits any machine:

| | formula | on 24 GB |
|---|---|---|
| concurrent sessions | `RAM × 5 / 24` | 5 |
| swap "tight" | `RAM / 3` | 8 G |
| swap "panic risk" | `RAM × 2 / 3` | 16 G |

Docker counts as one session.

## Freeing memory, by impact

1. Quit Docker Desktop - ~8 GB (the Linux VM, not the small host processes). Biggest single win. Keep it up only while a container is in use.
2. Close finished chats - 25-280 MB each, plus whatever dev servers and browsers they spawned.
3. `pkill -f chrome-headless-shell` - Playwright leftovers from UI verification.
4. `pkill -f "claude-[0-9]*.*scratchpad"` - orphaned dev servers whose chat is gone (reparented to PPID 1; archiving the chat does not kill them).
5. Stop a worktree `react-scripts` / `tsc --noEmit` - re-runnable, no state lost.

Never kill the dev servers in your main repo checkouts - those are yours, not an agent's.

## Not the cause

tmux is free (~2 MB RSS, 0.2 % CPU) - keep it. A terminal burning 70-90 % CPU is *rendering*
agent output; it costs CPU, not RAM, and does not cause panics. Separate terminal windows are
no cheaper than tmux panes - same streams, same renderer, plus one scrollback buffer and one
compositing surface each. The real saving is not watching a stream at all: detach the tmux
sessions you are not reading and the rendering cost goes to zero while the agent keeps working.
