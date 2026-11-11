#!/bin/bash
# Append one finished task to today's daily report (creates the day's file on first use).
# Usage: add.sh [-c <company>] [-p <project>] "<area>" "<what was done>" ["<Jira key or URL>"] ["<PR url> <PR url>..."]
#   area:    core | mobile | web | devops | support | other   (the kind of work)
#   company: work | personal | <any other>                  (who it is for; default: guessed from tags.conf)
#   project: free word, e.g. `website`, `api`        (optional; default: guessed from tags.conf)
# Env: DAILY_REPORT_DIR (default ~/daily-report) holds the day files and an optional tags.conf;
#      JIRA_BROWSE_URL (default https://example.atlassian.net/browse/); DAILY_REPORT_COMPANY (default work).
# Each line ends with one tag, #company or #company/project, so `grep '#work'` or report.py finds it.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="${DAILY_REPORT_DIR:-$HOME/daily-report}"; mkdir -p "$DIR"
TAGS="$DIR/tags.conf"; [ -f "$TAGS" ] || TAGS="$HERE/tags.conf"
company=""; project=""
while getopts "c:p:" o; do
  case "$o" in c) company="$OPTARG";; p) project="$OPTARG";; *) exit 1;; esac
done
shift $((OPTIND-1))
area="${1:?area}"; title="${2:?title}"; jira="${3:-}"; prs="${4:-}"
slug() { printf '%s' "$1" | tr '[:upper:] _' '[:lower:]--' | tr -cd 'a-z0-9-'; }
if [ -z "$company" ] || [ -z "$project" ]; then
  while IFS=$'\t' read -r re co pr || [ -n "$re" ]; do
    case "$re" in ''|'#'*) continue;; esac
    if printf '%s' "$area $title $jira $prs" | grep -Eiq -- "$re"; then
      [ -z "$company" ] && company="$co"
      [ -z "$project" ] && [ "$co" = "$company" ] && project="$pr"
      break
    fi
  done < "$TAGS"
fi
company="$(slug "${company:-${DAILY_REPORT_COMPANY:-work}}")"; project="$(slug "$project")"
tag="#$company"; [ -n "$project" ] && tag="$tag/$project"
file="$DIR/$(date +%F).md"
[ -f "$file" ] || printf '# Daily Report — %s (%s)\n\n' "$(date +%F)" "$(date +%A)" > "$file"
line="- \`$(date +%H:%M)\` **[$area]** $title"
case "$jira" in none|None|NONE|-|n/a|N/A) jira="";; esac
if [ -n "$jira" ]; then
  case "$jira" in http*) url="$jira"; key="${jira##*/}";; *) key="$jira"; url="${JIRA_BROWSE_URL:-https://example.atlassian.net/browse/}$jira";; esac
  line="$line — Jira: [$key]($url)"
fi
[ -n "$prs" ] && line="$line — PRs: $prs"
printf '%s %s\n' "$line" "$tag" >> "$file"
echo "$file"
# If the report folder is a git repo, commit (+ push if it has a remote); never fail the caller.
[ -d "$DIR/.git" ] && ( cd "$DIR" && git add -A . && git commit -qm "daily-report: $(date +%F) [$area] ${tag} ${title:0:60}" \
  && (git push -q >/dev/null 2>&1 &) ) >/dev/null 2>&1 || true
