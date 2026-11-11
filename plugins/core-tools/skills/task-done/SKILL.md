---
name: task-done
description: Tell the team on Zulip that I (the developer) finished a task — what was done, the PR(s) and whether they are merged or still open, and the Jira task if there is one. Use when the user says "task done", "inform/update/notify the team", "tell the team I finished X", "send a done update", "post this to the dev channel", or invokes /task-done. Picks channel + topic interactively and posts only after explicit approval.
---

# Task done → Zulip update

Posts **as the user** (their own `~/.zuliprc`), written in first person as the developer who did the work.
Script: `scripts/task_done.py` in this skill's folder (use the absolute path from the base directory).

## 1. Access
`python3 <skill>/scripts/task_done.py check`. No credentials → tell the user to download `.zuliprc`
(Zulip → Settings → Account & privacy → API key), save it as `~/.zuliprc`, `chmod 600`, and stop.
Never ask them to paste the key into chat.

## 2. Collect the facts (don't ask for what you can find)
Source, in order: the user's message / args → work done in this session → today's daily report
(`${DAILY_REPORT_DIR:-~/daily-report}/$(date +%F).md`, lines carry PR + Jira links). Several tasks done and none
named → ask which (or offer one combined update).

- **What was done:** 1–3 short bullets in plain words — the outcome for users/the team, not file names.
- **PR(s):** for each, `gh pr view <url> --json number,title,url,state,isDraft,mergedAt,baseRefName`.
  None given → look for the current branch's PR (`gh pr list --head <branch> --state all` inside the repo).
  Status wording: `MERGED` → "✅ merged into `<base>`"; `OPEN` → "🟡 open, waiting for review";
  draft → "📝 draft"; `CLOSED` → "⚪ closed without merge". No PR → "No PR (no code change)" only if true; else ask.
- **Jira:** key from the user, branch name, PR title/body (`[A-Z][A-Z0-9]+-\d+`). Link base:
  `task_done.py config jira_base` (if unset, ask once for the Jira browse URL, e.g.
  `https://<site>.atlassian.net/browse/`, and save with `config jira_base <url>`). If the Atlassian tools
  are connected, read the issue's summary/status to show it; if not, link only. No key → "Jira: none".
- **Optional:** deploy/migration notes, who should test, follow-ups — only if real.

## 3. Destination — ask every time
1. `task_done.py channels` → AskUserQuestion "Which channel?": the `(last used)` one first (strip that marker from the name), then up to 3
   likely dev channels from the list (user can type another via Other). Never invent a channel name.
2. `task_done.py topics --channel "<channel>"` → AskUserQuestion "Which topic?": first option
   **New topic: `<suggestion>`** (Jira → `PROJ-90: short title`; no Jira → short task title; ≤ 60 chars),
   then the 3 most relevant recent topics (prefer one that already mentions this Jira key/feature).

## 4. Message (Zulip markdown, short)
```
✅ **Done: <task title>**

- <what was done 1>
- <what was done 2>

**PR:** [<repo>#<n>](<url>) — ✅ merged into `development`
**Jira:** [PROJ-90](<url>) — <summary/status if known>   (or: **Jira:** none)
<optional one line: deploy note / please test X / follow-up>
```
Several PRs → one line each. No `@**all**` / `@**channel**` unless the user asks.

## 5. Preview → approval → send
1. Write the message to a temp file; run `send --channel … --topic … --file … --dry-run` and show the
   user channel › topic and the exact text.
2. Send **only after an explicit yes for this exact text** (any edit → preview again).
3. `send` (no `--dry-run`) prints the message link — give it to the user. Delete the temp file.
4. Fails → show the error; don't switch channel or retry on your own.
