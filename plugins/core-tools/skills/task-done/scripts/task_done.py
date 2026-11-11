#!/usr/bin/env python3
"""Zulip helper for the task-done skill (stdlib only).

Credentials: ~/.zuliprc (Zulip > Settings > Account & privacy > API key > "Download .zuliprc"),
or env ZULIP_EMAIL / ZULIP_API_KEY / ZULIP_SITE. Each person posts as themselves.
Per-person defaults (last channel, Jira base URL) live in ~/.config/task-done/config.json.

  task_done.py check                                  # who am I
  task_done.py channels                               # subscribed channels, last-used first
  task_done.py topics --channel "Dev" [-n 8] # most recent topics in a channel
  task_done.py send --channel C --topic T --file msg.md [--dry-run]
  task_done.py config [key [value]]                   # show / get / set a default
"""
import argparse
import base64
import configparser
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CONFIG = os.path.expanduser("~/.config/task-done/config.json")


def load_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2)


def creds():
    email, key, site = (os.environ.get(k) for k in ("ZULIP_EMAIL", "ZULIP_API_KEY", "ZULIP_SITE"))
    rc = os.path.expanduser(os.environ.get("ZULIP_RC", "~/.zuliprc"))
    if not (email and key and site) and os.path.exists(rc):
        cp = configparser.ConfigParser()
        cp.read(rc)
        api = cp["api"] if "api" in cp else {}
        email, key, site = email or api.get("email"), key or api.get("key"), site or api.get("site")
    if not (email and key and site):
        sys.exit("No Zulip credentials. Download your .zuliprc from Zulip (Settings > Account & privacy > "
                 "API key), save it as ~/.zuliprc (chmod 600), then retry.")
    return email, key, site.rstrip("/")


def call(method, path, data=None):
    email, key, site = creds()
    url = f"{site}/api/v1/{path}"
    body = None
    if data and method == "GET":
        url += "?" + urllib.parse.urlencode(data)
    elif data:
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{email}:{key}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), site
    except urllib.error.HTTPError as e:
        sys.exit(f"Zulip error {e.code}: {e.read().decode(errors='replace')}")


def subscriptions():
    res, _ = call("GET", "users/me/subscriptions")
    return {s["name"]: s["stream_id"] for s in res["subscriptions"]}


def hash_part(s):
    return urllib.parse.quote(s, safe="").replace("%", ".")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("channels")
    t = sub.add_parser("topics")
    t.add_argument("--channel", required=True)
    t.add_argument("-n", type=int, default=8)
    s = sub.add_parser("send")
    s.add_argument("--channel", required=True)
    s.add_argument("--topic", required=True)
    s.add_argument("--file", required=True)
    s.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("config")
    c.add_argument("key", nargs="?")
    c.add_argument("value", nargs="?")
    a = p.parse_args()
    cfg = load_config()

    if a.cmd == "check":
        res, site = call("GET", "users/me")
        print(f"OK: {res['full_name']} <{res['email']}> on {site}")
    elif a.cmd == "channels":
        names = sorted(subscriptions(), key=str.lower)
        last = cfg.get("channel")
        if last in names:
            names.remove(last)
            names.insert(0, last + "   (last used)")
        print("\n".join(names))
    elif a.cmd == "topics":
        subs = subscriptions()
        if a.channel not in subs:
            sys.exit(f"Not subscribed to channel '{a.channel}'. Run `channels`.")
        res, _ = call("GET", f"users/me/{subs[a.channel]}/topics")
        topics = sorted(res["topics"], key=lambda x: -x["max_id"])[: a.n]
        print("\n".join(x["name"] for x in topics) or "(no topics yet)")
    elif a.cmd == "send":
        with open(a.file) as f:
            content = f.read().strip()
        if len(a.topic) > 60:
            sys.exit(f"Topic is {len(a.topic)} chars; Zulip max is 60.")
        if len(content) > 10000:
            sys.exit(f"Message is {len(content)} chars; Zulip max is 10000.")
        if a.dry_run:
            print(f"--- DRY RUN: {a.channel} › {a.topic} ---\n{content}\n--- end ---")
            return
        subs = subscriptions()
        if a.channel not in subs:
            sys.exit(f"Not subscribed to channel '{a.channel}'. Run `channels`.")
        res, site = call("POST", "messages",
                         {"type": "stream", "to": a.channel, "topic": a.topic, "content": content})
        cfg["channel"] = a.channel
        save_config(cfg)
        sid = subs[a.channel]
        print(f"{site}/#narrow/channel/{sid}-{hash_part(a.channel)}/topic/{hash_part(a.topic)}/near/{res['id']}")
    elif a.cmd == "config":
        if a.key and a.value is not None:
            cfg[a.key] = a.value
            save_config(cfg)
        print(json.dumps(cfg.get(a.key) if a.key else cfg, indent=2))


if __name__ == "__main__":
    main()
