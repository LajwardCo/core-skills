# core-skills

Everyday skills for [Claude Code](https://claude.com/claude-code). Open to anyone.

```
/plugin marketplace add LajwardCo/core-skills
/plugin install core-tools@core-skills
```

| Skill | What it does |
|---|---|
| `todo` | A personal daily todo list, one file per day |
| `daily-report` | Logs finished work to a daily file; can post the day to your Zulip |
| `task-done` | Tells your team on Zulip that a task is finished, with PR and Jira links |
| `mac-guard` | Checks whether your Mac has headroom for another Claude session |
| `resume-any` | Lists and resumes any Claude Code chat across projects |
| `archive` | Archives, lists and restores Claude Code chats |

Nothing here holds a password, key or server. Skills that post (Zulip) use **your own** API key from
`~/.zuliprc`, show you the exact text first, and send only after you say yes.

Settings (all optional, environment variables): `TODO_DIR`, `DAILY_REPORT_DIR`, `DAILY_REPORT_COMPANY`,
`DAILY_REPORT_CHANNEL`, `JIRA_BROWSE_URL`.
