#!/bin/bash
# Daily TODO list. One file per day; unchecked items roll over from the previous day.
# Usage: todo.sh                      open/create today's file, list open items
#        todo.sh add [-c <company>] [-p <project>] "<task>" [area]   append an open item
#          company/project become a trailing #company/project tag
# Env: TODO_DIR (default ~/todos). A git repo there gets auto-commit (+ push if it has a remote).
#        todo.sh done <n>             tick open item #n (logs to daily report if it has an area)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="${TODO_DIR:-$HOME/todos}"; mkdir -p "$DIR"
# The daily-report skill sits next to this one in the core-tools plugin.
REPORT="$HERE/../../daily-report/scripts/add.sh"
file="$DIR/$(date +%F).md"

if [ ! -f "$file" ]; then
  printf '# TODO — %s (%s)\n\n' "$(date +%F)" "$(date +%A)" > "$file"
  prev="$(ls "$DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md 2>/dev/null | grep -v "$file" | sort | tail -1 || true)"
  [ -n "$prev" ] && grep -E '^- \[ \] ' "$prev" >> "$file" || true
fi

slug() { printf '%s' "$1" | tr '[:upper:] _' '[:lower:]--' | tr -cd 'a-z0-9-'; }
commit() { [ -d "$DIR/.git" ] || return 0; ( cd "$DIR" && git add -A . && git commit -qm "todos: $(date +%F) $1" \
  && (git push -q >/dev/null 2>&1 &) ) >/dev/null 2>&1 || true; }

case "${1:-}" in
  add)
    shift; company=""; project=""
    while getopts "c:p:" o; do
      case "$o" in c) company="$OPTARG";; p) project="$OPTARG";; *) exit 1;; esac
    done
    shift $((OPTIND-1))
    task="${1:?task}"; area="${2:-}"
    line="- [ ] "; [ -n "$area" ] && line="$line**[$area]** "
    tag=""
    if [ -n "$company" ]; then
      tag=" #$(slug "$company")"; [ -n "$project" ] && tag="$tag/$(slug "$project")"
    fi
    printf '%s%s%s\n' "$line" "$task" "$tag" >> "$file"
    commit "add ${task:0:60}" ;;
  done)
    n="${2:?item number}"
    item="$(grep -E '^- \[ \] ' "$file" | sed -n "${n}p")"
    [ -n "$item" ] || { echo "no open item #$n" >&2; exit 1; }
    awk -v n="$n" '/^- \[ \] /{c++; if(c==n){sub(/^- \[ \] /,"- [x] "); $0=$0" — done `'"$(date +%H:%M)"'`"}} {print}' \
      "$file" > "$file.tmp" && mv "$file.tmp" "$file"
    text="${item#- \[ \] }"
    if [[ "$text" =~ ^\*\*\[([a-z]+)\]\*\*\ (.*)$ ]]; then
      area="${BASH_REMATCH[1]}"; what="${BASH_REMATCH[2]}"; flags=()
      # carry a trailing #company[/project] tag over to the daily report
      if [[ "$what" =~ ^(.*[^[:space:]])[[:space:]]+#([a-z][a-z0-9-]*)(/([a-z0-9-]+))?$ ]]; then
        what="${BASH_REMATCH[1]}"; flags=(-c "${BASH_REMATCH[2]}")
        [ -n "${BASH_REMATCH[4]}" ] && flags+=(-p "${BASH_REMATCH[4]}")
      fi
      [ -x "$REPORT" ] && "$REPORT" ${flags[@]+"${flags[@]}"} "$area" "$what" >/dev/null || true
    fi
    commit "done ${text:0:60}" ;;
  "") ;;
  *) echo "usage: todo.sh [add [-c company] [-p project] \"<task>\" [area] | done <n>]" >&2; exit 1 ;;
esac

echo "$file"
grep -E '^- \[ \] ' "$file" | nl -w2 -s'. ' | sed 's/- \[ \] //' || echo "(no open items)"
