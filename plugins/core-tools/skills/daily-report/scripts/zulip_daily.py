#!/usr/bin/env python3
"""Post your daily report to the Zulip 'Daily Reports' channel.

Reads ~/.zuliprc (same credentials as the task-done skill). Posts as you.

  zulip_daily.py check
  zulip_daily.py lines   [--date YYYY-MM-DD]   # raw lines of that day's report file
  zulip_daily.py topic   [--date YYYY-MM-DD]   # existing topic for that day, or the one to create
  zulip_daily.py topics  [-n 15]               # recent topics in the channel
  zulip_daily.py posted  [--date YYYY-MM-DD]   # did I already post in that day's topic?
  zulip_daily.py send --file msg.md [--date YYYY-MM-DD] [--topic T] [--dry-run]
"""
import argparse, base64, configparser, json, os, re, sys, urllib.parse, urllib.request
from datetime import date, datetime, timedelta

CHANNEL = os.environ.get("DAILY_REPORT_CHANNEL") or "Daily Reports"
REPORT_DIR = os.path.expanduser(os.environ.get("DAILY_REPORT_DIR") or "~/daily-report")
RC = os.path.expanduser("~/.zuliprc")
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def creds():
    if not os.path.exists(RC):
        sys.exit("No ~/.zuliprc. Zulip > Settings > Account & privacy > API key, save as ~/.zuliprc, chmod 600.")
    c = configparser.ConfigParser(); c.read(RC)
    a = c["api"]
    return a["site"].rstrip("/"), a["email"], a["key"]


def call(method, path, params=None):
    site, email, key = creds()
    auth = base64.b64encode(f"{email}:{key}".encode()).decode()
    data = urllib.parse.urlencode(params or {})
    url = f"{site}/api/v1{path}"
    if method == "GET":
        url += ("?" + data) if data else ""
        req = urllib.request.Request(url, headers={"Authorization": "Basic " + auth})
    else:
        req = urllib.request.Request(url, data=data.encode(), method=method,
                                     headers={"Authorization": "Basic " + auth})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        sys.exit(f"Zulip error {e.code}: {e.read().decode()[:400]}")


def the_date(args):
    if getattr(args, "date", None):
        return datetime.strptime(args.date, "%Y-%m-%d").date()
    return date.today()


def canonical_topic(d):
    """House pattern, as used in the channel: '3 Nov - 2026'."""
    return f"{d.day} {MON[d.month - 1]} - {d.year}"


def recent_topics(n=25):
    site, email, key = creds()
    chans = call("GET", "/streams")["streams"]
    sid = next((s["stream_id"] for s in chans if s["name"] == CHANNEL), None)
    if sid is None:
        sys.exit(f"Channel {CHANNEL!r} not found (or not subscribed).")
    return sid, [t["name"] for t in call("GET", f"/users/me/{sid}/topics")["topics"]][:n]


def match_topic(d, topics):
    """Find an existing topic for this date whatever spelling the team used."""
    mon = MON[d.month - 1].lower()
    full = datetime(d.year, d.month, d.day).strftime("%B").lower()
    for t in topics:
        low = t.lower()
        if not re.search(rf"\b{d.day}\b", low):
            continue
        if (mon in low or full in low) and str(d.year) in low:
            return t
    return None


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    for name in ("lines", "topic", "posted"):
        s = sub.add_parser(name); s.add_argument("--date")
    s = sub.add_parser("topics"); s.add_argument("-n", type=int, default=15)
    s = sub.add_parser("send")
    s.add_argument("--file", required=True); s.add_argument("--date")
    s.add_argument("--topic"); s.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if a.cmd == "check":
        me = call("GET", "/users/me")
        site, _, _ = creds()
        print(f"OK: {me['full_name']} <{me['email']}> on {site} -> #{CHANNEL}")
        return

    if a.cmd == "topics":
        _, topics = recent_topics(a.n)
        print("\n".join(topics))
        return

    d = the_date(a)

    if a.cmd == "lines":
        f = os.path.join(REPORT_DIR, f"{d:%Y-%m-%d}.md")
        if not os.path.exists(f):
            sys.exit(f"No report file for {d} ({f}).")
        sys.stdout.write(open(f).read())
        return

    if a.cmd == "topic":
        _, topics = recent_topics(40)
        hit = match_topic(d, topics)
        print(hit if hit else canonical_topic(d))
        print("existing" if hit else "new", file=sys.stderr)
        return

    if a.cmd == "posted":
        _, topics = recent_topics(40)
        topic = match_topic(d, topics) or canonical_topic(d)
        _, email, _ = creds()
        narrow = json.dumps([{"operator": "channel", "operand": CHANNEL},
                             {"operator": "topic", "operand": topic},
                             {"operator": "sender", "operand": email}])
        msgs = call("GET", "/messages", {"anchor": "newest", "num_before": 20,
                                         "num_after": 0, "narrow": narrow})["messages"]
        print(f"{len(msgs)} message(s) by me in {topic!r}")
        for m in msgs:
            print(" -", m["content"].splitlines()[0][:100])
        return

    if a.cmd == "send":
        body = open(a.file).read().strip()
        if not body:
            sys.exit("Empty message file.")
        if a.topic:
            topic = a.topic
        else:
            _, topics = recent_topics(40)
            topic = match_topic(d, topics) or canonical_topic(d)
        if a.dry_run:
            print(f"DRY RUN -> #{CHANNEL} > {topic}\n{'-' * 60}\n{body}\n{'-' * 60}")
            return
        r = call("POST", "/messages", {"type": "stream", "to": CHANNEL,
                                       "topic": topic, "content": body})
        site, _, _ = creds()
        enc = lambda s: urllib.parse.quote(s.replace(" ", "."), safe="")
        print(f"Sent. {site}/#narrow/channel/{enc(CHANNEL)}/topic/{enc(topic)}/near/{r['id']}")


if __name__ == "__main__":
    main()
