---
name: daily-report
description: Write what was just done into your daily report ($DAILY_REPORT_DIR/YYYY-MM-DD.md, default ~/daily-report) with area, company/project tag, Jira task and PR links; post the day's report to the Zulip 'Daily Reports' channel; also find past work by company, project or date ("what did I do on Oct 9"). Use AUTOMATICALLY whenever a piece of work is finished, and when the user says "write it in my daily report", "add to daily report", "log this", "/daily-report", "post my daily report", "send the report to Zulip", "end of day", or asks to see or summarize the reports.
---

# daily-report

One line per finished task, appended to today's file by `scripts/add.sh` (in this skill's folder —
use the absolute path from the skill's base directory). Every line carries a `#company/project` tag
so work stays separate and searchable.

**Settings (env vars, all optional):**

| Var | Default | Meaning |
|---|---|---|
| `DAILY_REPORT_DIR` | `~/daily-report` | where the day files live. Make it a git repo to get auto-commit (+ push if it has a remote). |
| `DAILY_REPORT_COMPANY` | `work` | company tag when nothing else matches |
| `JIRA_BROWSE_URL` | `https://example.atlassian.net/browse/` | prefix for a bare Jira key |
| `DAILY_REPORT_CHANNEL` | `Daily Reports` | Zulip channel for the end-of-day post |

Auto-tag rules: `scripts/tags.conf`; copy it to `$DAILY_REPORT_DIR/tags.conf` to customise.

## When to log (default: always, without being asked)

Log **every finished piece of work** the moment it is done — a merged or opened PR, a deployed
change, a fixed bug, an infra task, a review, a document, a decision carried out. Don't ask first:

1. Finish the work.
2. Write the line (Steps below) straight away, as part of the same reply.
3. Say in one line that it was logged.

Skip only when nothing was actually finished (exploration, a question, an unexecuted plan), the
same work is already a line in today's file, or the user says not to log it.

## Steps
1. Gather from the conversation; ask only if truly missing:
   - **what**: one line, outcome-first, specific. Related steps of one task → one line; separate tasks → separate lines.
   - **area**: `core` | `mobile` | `web` | `devops` | `support` | `other`.
   - **company** (`-c`): who it is for — `work`, `personal`, or another name the user gives.
   - **project** (`-p`, optional slug): e.g. `website`, `api`. Unsure → omit both flags; `tags.conf` guesses.
   - **Jira**: key like `PROJ-89` or full URL — from branch name, PR title/body, commits, the user's words. None → `none` (never invent one).
   - **PRs**: full URLs of every PR for the work (`gh pr view --json url`). Say "merged" in the text if merged.
2. Run:
   ```
   <skill>/scripts/add.sh [-c <company>] [-p <project>] "<area>" "<what>" "<Jira key|URL|none>" "<PR url> <PR url>"
   ```
   It prints the file path.
3. Reply with the line written. One line.

## Looking things up
Use `<skill>/scripts/report.py` (don't grep by hand):
- `report.py -c work -p website` — one company/project, all days
- `report.py --days 7` — last 7 days
- `report.py --date 2026-10-09 --group company` — one day, split by company
- `report.py --summary --days 30` — counts per company/project

Flags: `-a area`, `--from/--to YYYY-MM-DD`, `--group date|company|project`.

## End of day → post the report to Zulip

The team's daily reports go to the Zulip channel **Daily Reports**, one topic per day named
`<D> <Mon> - <YYYY>` (e.g. `3 Nov - 2026`). The topic is usually already created by someone else —
reuse it; create it only if missing. Script: `scripts/zulip_daily.py`. Credentials: `~/.zuliprc`
(Zulip → Settings → Account & privacy → API key → Download `.zuliprc`, `chmod 600`); `zulip_daily.py check` verifies them.

**Offer it** when the day looks finished (user signs off / "end of day" / "post my report", or it
is late and today's file has lines). Never post silently — the channel is visible to the team.

1. `zulip_daily.py posted --date <YYYY-MM-DD>` — already posted? stop, say so.
2. `zulip_daily.py lines --date <YYYY-MM-DD>` — the day's raw lines.
3. Write the message yourself from those lines:
   ```
   <D Mon> Tasks:

   - <one short line per task — the outcome, in plain words a non-developer gets>
   ```
   - Short bullets, no hype, no file names. Merge one feature's several entries into one bullet.
   - Link where it helps: `[PROJ-181](<jira url>)`, PR as `[backend#1277](url)`.
   - Mark what shipped: "merged", "live on production", "open, waiting for review". English.
4. Preview: write to a temp file, `zulip_daily.py send --file <tmp> --date <YYYY-MM-DD> --dry-run`,
   show the user channel › topic and the exact text.
5. Send **only after an explicit yes for that exact text** (any edit → preview again):
   `zulip_daily.py send --file <tmp> --date <YYYY-MM-DD>` — prints the link. Give it, delete the temp file.
6. `--topic "<name>"` overrides the topic. A missed day can be posted later with `--date`.

## Rules
- Never edit past days' lines; only append. To correct today's entry, edit the line in the file.
- English, plain words. Match the style of existing lines in the day's file.
- Several tasks → one `add.sh` call per task. Don't add a duplicate of a line already in the file.
- The Zulip post summarizes the file — never post without the lines existing first.
