---
name: todo
description: Your personal daily todo list — one file per day in $TODO_DIR (default ~/todos), unchecked items roll over to the next day, ticking an item with an area also logs it to your daily report. Use for "my todo", "my todos", "add to my todo", "what's on my list", "tick/done item 3", "/todo".
---

# todo

Script: `<skill>/scripts/todo.sh` (absolute path from this skill's base directory). Personal to
whoever runs it: files live in `$TODO_DIR` (default `~/todos`), nothing is shared or posted.
Make that folder a git repo to get auto-commit (+ push if it has a remote).

| Ask | Run |
|---|---|
| what's on my list | `todo.sh` — print the numbered open items as they come |
| add something | `todo.sh add [-c <company>] [-p <project>] "<task>" [area]` |
| tick item n | `todo.sh done <n>` |

- **area** (optional): `core` | `mobile` | `web` | `devops` | `support` | `other`. An item **with** an
  area is logged to the daily report (the `daily-report` skill's `add.sh`) when ticked, keeping its
  `#company/project` tag. Example: `-c work -p website`.
- Unchecked items from the latest earlier day are copied into today's file on first use.
- The day files are plain Markdown. Editing them by hand is fine.
- Before `done <n>`, run `todo.sh` if the numbering might have changed, and say which item you ticked.
