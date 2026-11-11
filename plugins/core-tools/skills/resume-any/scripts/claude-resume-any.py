#!/usr/bin/env python3
"""Resume ANY chat of this account (all projects) from INSIDE a running Claude Code session.

usage:
  claude-resume-any.py list [limit]   -> numbered table on stdout, caches the rows
  claude-resume-any.py go <n>         -> exit this chat and relaunch chat #n in the SAME window/pane

Window handoff: tmux pane -> send-keys; plain Terminal.app tab -> AppleScript `do script`.
"""
import sys, os, re, json, glob, time, subprocess, shlex

_STATE = os.path.expanduser(os.environ.get("XDG_CACHE_HOME") or "~/.cache") + "/resume-any"
os.makedirs(_STATE, exist_ok=True)
CACHE = _STATE + "/cache.json"
LOG = _STATE + "/resume-any.log"
SHELLS = ("zsh", "bash", "fish", "sh", "login")


def log(m):
    with open(LOG, "a") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def cfg_dir():
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def acct_cmd():
    # Default config dir -> plain `claude`; a second account/profile -> keep its config dir.
    d = cfg_dir().rstrip("/")
    if d == os.path.expanduser("~/.claude"):
        return "claude"
    return f"CLAUDE_CONFIG_DIR={shlex.quote(d)} claude"


def ago(t):
    s = max(0, time.time() - t)
    for n, u in ((86400 * 7, "w"), (86400, "d"), (3600, "h"), (60, "m")):
        if s >= n:
            return f"{int(s // n)}{u}"
    return "now"


def load(limit):
    files = sorted(glob.glob(cfg_dir() + "/projects/*/*.jsonl"), key=os.path.getmtime, reverse=True)[: limit * 4]
    out = []
    for f in files:
        cwd = title = br = None
        try:
            with open(f, "rb") as fh:
                raw = fh.read()
            ms = re.findall(rb'"customTitle":"((?:[^"\\]|\\.)*)"', raw)
            custom = json.loads('"' + ms[-1].decode() + '"') if ms else None
            for l in raw.split(b"\n")[:400]:
                try:
                    d = json.loads(l)
                except Exception:
                    continue
                cwd = cwd or d.get("cwd")
                br = br or d.get("gitBranch")
                if not title and d.get("type") == "user" and not d.get("isSidechain"):
                    c = d.get("message", {}).get("content")
                    if isinstance(c, list):
                        c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                    if isinstance(c, str) and c.strip() and not c.lstrip().startswith("<"):
                        title = " ".join(c.split())[:90]
                if cwd and title and br:
                    break
        except Exception:
            continue
        if cwd and (custom or title) and os.path.isdir(cwd):
            out.append(dict(mt=os.path.getmtime(f), cwd=cwd, br=br,
                            id=os.path.basename(f)[:-6], title=custom or title))
        if len(out) >= limit:
            break
    return out


def cmd_list(limit, query=None):
    rows = load(limit if not query else max(limit, 400))
    if query:
        q = query.lower()
        rows = [r for r in rows if q in (r["title"] + " " + r["cwd"] + " " + (r["br"] or "")).lower()][:limit]
    me = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    json.dump(dict(acct=acct_cmd(), rows=rows), open(CACHE, "w"))
    print(f"{acct_cmd()} - {len(rows)} chats, all projects" + (f" matching '{query}'" if query else "") + "\n")
    print(f"{'#':>3}  {'AGE':<5} {'PROJECT':<22} {'BRANCH':<14} TITLE")
    for i, r in enumerate(rows, 1):
        mark = " *" if r["id"] == me else "  "
        print(f"{i:>3}{mark}{ago(r['mt']):<5} {os.path.basename(r['cwd'])[:22]:<22} "
              f"{(r['br'] or '-')[:14]:<14} {r['title'][:70]}")
    if any(r["id"] == me for r in rows):
        print("\n* = this chat")


def my_pids():
    pids, p = [], os.getpid()
    for _ in range(12):
        pids.append(p)
        o = subprocess.run(["ps", "-o", "ppid=", "-p", str(p)], capture_output=True, text=True).stdout.strip()
        if not o or o == "1":
            break
        p = int(o)
    return pids


def my_tty():
    for p in my_pids():
        t = subprocess.run(["ps", "-o", "tty=", "-p", str(p)], capture_output=True, text=True).stdout.strip()
        if t and t != "??":
            return "/dev/" + t
    return None


def my_pane():
    if os.environ.get("TMUX_PANE"):
        return os.environ["TMUX_PANE"]
    o = subprocess.run(["tmux", "list-panes", "-a", "-F", "#{pane_id} #{pane_pid}"],
                       capture_output=True, text=True).stdout
    mine = set(my_pids())
    for line in o.splitlines():
        try:
            pid_, ppid_ = line.split()
        except ValueError:
            continue
        if int(ppid_) in mine:
            return pid_
    return None


def launch_tmux(pane, cmd, title):
    sh = f"""exec >> {shlex.quote(LOG)} 2>&1
tmux send-keys -t {pane} Escape C-u '/exit' Enter
ok=0
for i in $(seq 1 60); do sleep 0.5; c=$(tmux display -p -t {pane} '#{{pane_current_command}}')
  case "$c" in zsh|bash|fish|sh) ok=1; break;; esac; done
echo "tmux exit wait ok=$ok last=$c"
[ $ok = 0 ] && {{ tmux display-message -t {pane} 'resume-any: claude did not exit'; exit 1; }}
sleep 0.7
tmux send-keys -t {pane} {shlex.quote(cmd)} Enter
sleep 3
tmux select-pane -t {pane} -T {shlex.quote(title)}
echo done
"""
    subprocess.Popen(["sh", "-c", sh], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def launch_terminal(tty, cmd):
    subprocess.Popen([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume-any-handoff.py"),
                      tty, cmd, cfg_dir(), os.environ.get("CLAUDE_CODE_SESSION_ID", "")],
                     start_new_session=True, stdout=open(LOG, "a"), stderr=subprocess.STDOUT)


def cmd_go(n):
    d = json.load(open(CACHE))
    rows = d["rows"]
    if not 1 <= n <= len(rows):
        sys.exit(f"pick 1..{len(rows)}")
    r = rows[n - 1]
    if r["id"] == os.environ.get("CLAUDE_CODE_SESSION_ID", ""):
        sys.exit("that is this chat")
    cmd = f"cd {shlex.quote(r['cwd'])} && {d['acct']} --resume {r['id']}"
    pane = my_pane()
    if pane:
        launch_tmux(pane, cmd, r["title"].replace("'", "")[:60])
        where = f"tmux pane {pane}"
    else:
        tty = my_tty()
        if not tty:
            sys.exit("no tmux pane and no tty - run `" + cmd + "` yourself")
        launch_terminal(tty, cmd)
        where = f"Terminal tab {tty}"
    print(f"resuming in {where}: {r['title'][:60]}\n  {cmd}")


if __name__ == "__main__":
    a = sys.argv[1:] or ["list"]
    if a[0] == "list":
        rest = a[1:]
        lim = 30
        if rest and rest[0].isdigit():
            lim = int(rest.pop(0))
        cmd_list(lim, " ".join(rest) or None)
    elif a[0] == "go":
        cmd_go(int(a[1]))
    else:
        sys.exit(__doc__)
