#!/usr/bin/env python3
"""Detached: wait for this chat's turn to end, send /exit to its Terminal.app tab, then run <cmd> there.
usage: resume-any-handoff.py <tty> <cmd> <config-dir> <session-id>"""
import sys, os, time, glob, subprocess

tty, cmd, cfg, sid = sys.argv[1:5]


def osa(s):
    return subprocess.run(["osascript", "-e", s], capture_output=True, text=True).stdout.strip()


# 1. wait until the running turn is done (transcript idle 4s), max 60s
f = (glob.glob(os.path.expanduser(cfg) + f"/projects/*/{sid}.jsonl") or [None])[0]
for _ in range(120):
    time.sleep(0.5)
    if f and os.path.exists(f) and time.time() - os.path.getmtime(f) > 4:
        break

# 2. locate the tab by tty
loc = osa(f'''tell application "Terminal"
 repeat with w in windows
  set n to count of tabs of w
  repeat with i from 1 to n
   if tty of tab i of w is "{tty}" then return (id of w as string) & "," & (i as string)
  end repeat
 end repeat
end tell''')
if not loc:
    sys.exit("resume-any: Terminal tab not found for " + tty)
wid, tix = loc.split(",")


def do(c):
    esc = c.replace("\\", "\\\\").replace('"', '\\"')
    osa(f'tell application "Terminal" to do script "{esc}" in tab {tix} of window id {wid}')


def procs():
    return osa(f'tell application "Terminal" to get processes of tab {tix} of window id {wid}')


if "claude" not in procs():
    do(cmd)
    sys.exit()

# 3. quit the current chat, wait for the shell prompt, relaunch
do("/exit")
for _ in range(80):
    time.sleep(0.5)
    if "claude" not in procs():
        break
else:
    sys.exit("resume-any: claude did not exit")
time.sleep(1.0)
do(cmd)
