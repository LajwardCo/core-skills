#!/usr/bin/env python3
"""Archive Claude Code CLI chats: hide them from `claude --resume` without deleting them.

A chat is a transcript at <config>/projects/<project>/<session-id>.jsonl (plus an optional
<session-id>/ folder for subagents). Archiving moves both to <config>/archived-sessions/<project>/
and records it in <config>/archived-sessions/ledger.json. Restoring moves them back.

The running chat cannot be moved while Claude Code is still writing it, so `this` marks it
"pending" and starts a detached watcher that moves it once the Claude Code process exits.
`sweep` (run by every other command too) finishes any pending entry whose process is gone.

Usage:
  archive.py this [--title T]     archive the chat running this command (CLAUDE_CODE_SESSION_ID)
             [--session ID --pid-parent]   (as the archive mod calls it)
  archive.py close <session-id>   the session ended (/clear): move a pending chat now
  archive.py id <session-id>      archive another (not running) chat by id or id prefix
  archive.py list [--all]         archived chats (--all: include restored/cancelled)
  archive.py restore <id-prefix>  move a chat back so `claude --resume` shows it again
  archive.py cancel               un-archive the running chat before it is moved
  archive.py sweep                move pending chats whose process has exited, and fold back
                                  transcripts that reappeared under projects/ after archiving
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

CONFIG = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")
PROJECTS = os.path.join(CONFIG, "projects")
ARCHIVE = os.path.join(CONFIG, "archived-sessions")
LEDGER = os.path.join(ARCHIVE, "ledger.json")


def load():
    try:
        with open(LEDGER) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"v": 1, "sessions": {}}


def save(data):
    os.makedirs(ARCHIVE, exist_ok=True)
    tmp = LEDGER + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, LEDGER)


def alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def find_transcript(sid):
    hits = glob.glob(os.path.join(PROJECTS, "*", f"{sid}.jsonl"))
    return hits[0] if hits else None


def resolve(prefix, where):
    """Full session id for a prefix, from live transcripts or the ledger."""
    ids = set()
    if where in ("live", "any"):
        ids |= {os.path.basename(p)[:-6] for p in glob.glob(os.path.join(PROJECTS, "*", f"{prefix}*.jsonl"))}
    if where in ("ledger", "any"):
        ids |= {s for s in load()["sessions"] if s.startswith(prefix)}
    if len(ids) != 1:
        sys.exit(f"{'no' if not ids else 'ambiguous'} session matches '{prefix}'" + (f": {sorted(ids)}" if ids else ""))
    return ids.pop()


def title_of(path):
    title, first = "", ""
    with open(path, errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") in ("custom-title", "ai-title") and (d.get("customTitle") or d.get("aiTitle")):
                title = d.get("customTitle") or d.get("aiTitle")
            elif d.get("type") == "summary" and d.get("summary") and not title:
                title = d["summary"]
            elif not first and d.get("type") == "user" and isinstance(d.get("message", {}).get("content"), str):
                first = d["message"]["content"].strip().splitlines()[0][:80] if d["message"]["content"].strip() else ""
    return title or first or "(untitled)"


def reap(sid):
    """Kill leftover background jobs (Bash run_in_background, tsc/test/dev-server watchers) this
    chat started. They run detached under /private/tmp/claude-*/.../<sid>/scratchpad/..., so any
    process whose argv still names this session id belongs to it and nothing else."""
    try:
        out = subprocess.run(["pgrep", "-f", sid], capture_output=True, text=True).stdout
    except OSError:
        return 0
    pids = [int(p) for p in out.split() if p.strip().isdigit() and int(p) != os.getpid()]
    for pid in pids:
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    if pids:
        time.sleep(1)
        for pid in pids:
            try:
                os.kill(pid, 0)
                os.kill(pid, 9)
            except OSError:
                pass
    return len(pids)


def move(sid, entry):
    src = find_transcript(sid)
    if not src:
        return False
    proj = os.path.basename(os.path.dirname(src))
    dst_dir = os.path.join(ARCHIVE, proj)
    os.makedirs(dst_dir, exist_ok=True)
    shutil.move(src, os.path.join(dst_dir, f"{sid}.jsonl"))
    side = os.path.join(os.path.dirname(src), sid)
    if os.path.isdir(side):
        shutil.move(side, os.path.join(dst_dir, sid))
    killed = reap(sid)
    entry.update(status="archived", project=proj, moved_at=datetime.now().isoformat(timespec="seconds"), reaped=killed)
    return True


UUID_RE = re.compile(r'"uuid":"([0-9a-f-]{36})"')


def reclaim(sid, entry, grace=60):
    """Fold back a transcript that reappeared under projects/ after the chat was archived.

    Claude Code is still running when the file is moved and keeps writing to the same *path*,
    which re-creates <sid>.jsonl (usually just the /archive and /clear lines, sometimes a whole
    continued chat) — so the chat shows up in `claude --resume` again. Once nothing has written
    it for `grace` seconds, append its new lines (by uuid) to the archived copy and drop it.
    """
    if sid == os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return False
    live = find_transcript(sid)
    dst = os.path.join(ARCHIVE, entry.get("project") or "", f"{sid}.jsonl")
    if not live or not os.path.exists(dst):
        return False
    try:
        if time.time() - os.path.getmtime(live) < grace:
            return False
    except OSError:
        return False
    seen = set()
    with open(dst, errors="replace") as fh:
        for line in fh:
            m = UUID_RE.search(line)
            if m:
                seen.add(m.group(1))
    added = 0
    with open(live, errors="replace") as src, open(dst, "a") as out:
        for line in src:
            m = UUID_RE.search(line)
            if m and m.group(1) in seen:
                continue
            out.write(line if line.endswith("\n") else line + "\n")
            added += 1
    os.remove(live)
    side = os.path.join(os.path.dirname(live), sid)
    if os.path.isdir(side):
        dst_side = os.path.join(os.path.dirname(dst), sid)
        os.makedirs(dst_side, exist_ok=True)
        for name in os.listdir(side):
            target = os.path.join(dst_side, name)
            if not os.path.exists(target):
                shutil.move(os.path.join(side, name), target)
        shutil.rmtree(side, ignore_errors=True)
    entry["reclaimed"] = entry.get("reclaimed", 0) + added
    entry["reclaimed_at"] = datetime.now().isoformat(timespec="seconds")
    return True


def sweep(quiet=False):
    data = load()
    done = back = 0
    for sid, e in data["sessions"].items():
        if e.get("status") == "pending" and not alive(e.get("pid")) and move(sid, e):
            done += 1
        if e.get("status") == "archived" and reclaim(sid, e):
            back += 1
    if done or back:
        save(data)
    if not quiet:
        if done:
            print(f"swept {done} pending chat(s) into the archive")
        if back:
            print(f"re-archived {back} chat(s) that reappeared under projects/")


def mark(sid, pid, title=None):
    path = find_transcript(sid)
    if not path:
        sys.exit(f"transcript for {sid} not found under {PROJECTS}")
    data = load()
    e = data["sessions"].setdefault(sid, {})
    e.update(
        title=title or title_of(path),
        project=os.path.basename(os.path.dirname(path)),
        archived_at=datetime.now().isoformat(timespec="seconds"),
        status="pending",
        pid=int(pid) if pid else None,
    )
    if not alive(pid):
        move(sid, e)
    save(data)
    return e


def opt(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def cmd_this(args):
    # --session/--pid-parent: called by the archive mod, which knows the session id but not the env.
    sid = opt(args, "--session") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    pid = os.getppid() if "--pid-parent" in args else os.environ.get("CLAUDE_PID")
    if not sid:
        sys.exit("CLAUDE_CODE_SESSION_ID is not set — run this from inside a Claude Code session")
    title = opt(args, "--title")
    e = mark(sid, pid, title)
    if e["status"] == "pending":
        # Detached watcher: survives this tool call and moves the chat when Claude Code exits.
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "_finish", sid],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    print(json.dumps({"session": sid, **e}, ensure_ascii=False))


def cmd_finish(sid):
    while True:
        e = load()["sessions"].get(sid)
        if not e or e.get("status") != "pending":
            return  # cancelled, restored or already moved (close() spawns its own reclaim watcher)
        if not alive(e.get("pid")):
            break
        time.sleep(3)
    time.sleep(2)  # let Claude Code flush its last lines
    data = load()
    e = data["sessions"].get(sid)
    if e and e.get("status") == "pending" and move(sid, e):
        save(data)
        watch_reclaim(sid)


def watch_reclaim(sid):
    """Detached watcher that folds back the transcript Claude Code re-creates after the move.
    Spawned after move() ran, because move() reaps every process whose argv names this session."""
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "_reclaim", sid],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def cmd_reclaim(sid):
    for _ in range(20):
        time.sleep(15)
        data = load()
        e = data["sessions"].get(sid)
        if not e or e.get("status") != "archived":
            return
        if reclaim(sid, e):
            save(data)
            return


def cmd_close(sid):
    """The session ended (e.g. /clear): move a pending chat now, without waiting for the process."""
    data = load()
    e = data["sessions"].get(sid)
    if e and e.get("status") == "pending" and move(sid, e):
        save(data)
        watch_reclaim(sid)
        print(f"archived {sid}")


def cmd_id(args):
    sid = resolve(args[0], "live")
    if sid == os.environ.get("CLAUDE_CODE_SESSION_ID"):
        sys.exit("that is the running chat — use `this`")
    e = mark(sid, None)
    print(json.dumps({"session": sid, **e}, ensure_ascii=False))


def cmd_list(args):
    rows = [(s, e) for s, e in load()["sessions"].items() if "--all" in args or e.get("status") in ("pending", "archived")]
    rows.sort(key=lambda r: r[1].get("archived_at", ""), reverse=True)
    if not rows:
        print("no archived chats")
        return
    for sid, e in rows:
        print(f"{sid[:8]}  {e.get('archived_at', '')[:16]}  {e.get('status', ''):9}  {e.get('project', '')[-40:]:40}  {e.get('title', '')}")


def cmd_restore(args):
    sid = resolve(args[0], "ledger")
    data = load()
    e = data["sessions"][sid]
    if e.get("status") == "pending":
        e["status"] = "cancelled"
        save(data)
        print(f"{sid} was not moved yet — un-archived")
        return
    src = os.path.join(ARCHIVE, e["project"], f"{sid}.jsonl")
    if not os.path.exists(src):
        sys.exit(f"archived transcript missing: {src}")
    dst_dir = os.path.join(PROJECTS, e["project"])
    os.makedirs(dst_dir, exist_ok=True)
    shutil.move(src, os.path.join(dst_dir, f"{sid}.jsonl"))
    side = os.path.join(ARCHIVE, e["project"], sid)
    if os.path.isdir(side):
        shutil.move(side, os.path.join(dst_dir, sid))
    e.update(status="restored", restored_at=datetime.now().isoformat(timespec="seconds"))
    save(data)
    print(f"restored {sid} — resume with: claude --resume {sid}")


def cmd_cancel(args):
    sid = opt(args, "--session") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    data = load()
    e = data["sessions"].get(sid or "")
    if not e or e.get("status") != "pending":
        sys.exit("the running chat is not pending archive")
    e["status"] = "cancelled"
    save(data)
    print(f"{sid} un-archived")


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "_finish":
        return cmd_finish(rest[0])
    if cmd == "_reclaim":
        return cmd_reclaim(rest[0])
    if cmd == "close" and rest:
        return cmd_close(rest[0])
    sweep(quiet=cmd != "sweep")
    if cmd == "this":
        cmd_this(rest)
    elif cmd == "id" and rest:
        cmd_id(rest)
    elif cmd == "list":
        cmd_list(rest)
    elif cmd == "restore" and rest:
        cmd_restore(rest)
    elif cmd == "cancel":
        cmd_cancel(rest)
    elif cmd != "sweep":
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
