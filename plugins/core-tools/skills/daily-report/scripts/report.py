#!/usr/bin/env python3
"""Query the daily reports by company / project / area / date.

  report.py -c work                      everything for work, all days
  report.py -c work -p website          one project
  report.py -c personal --days 7            personal work, last 7 days
  report.py --date 2026-10-09 --group company   one day, split by company
  report.py --summary --days 30             counts per company/project

Old lines without a tag are tagged on the fly with the rules in tags.conf.
"""
import argparse, datetime, glob, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.expanduser(os.environ.get("DAILY_REPORT_DIR") or "~/daily-report")
TAGS = os.path.join(DIR, "tags.conf") if os.path.exists(os.path.join(DIR, "tags.conf")) else os.path.join(HERE, "tags.conf")
LINE = re.compile(r"^- `(\d\d:\d\d)` \*\*\[([^\]]+)\]\*\* (.*)$")
LINK = re.compile(r"\]\(https?://[^)]*\)")
TAG = re.compile(r"\s#([a-z][a-z0-9-]*)(?:/([a-z0-9-]+))?\s*$")


def rules():
    out = []
    for raw in open(TAGS, encoding="utf-8"):
        if raw.strip() and not raw.startswith("#"):
            re_, co, *pr = raw.rstrip("\n").split("\t")
            out.append((re.compile(re_, re.I), co, (pr[0] if pr else "")))
    return out


def tag_of(area, rest, rl):
    m = TAG.search(" " + rest)
    if m:
        return m.group(1), m.group(2) or "", TAG.sub("", " " + rest).strip()
    plain = LINK.sub("]", rest)  # drop link targets so "atlassian" never matches "atlas"
    for rx, co, pr in rl:
        if rx.search(f"{area} {plain}"):
            return co, pr, rest
    return "work", "", rest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--company")
    ap.add_argument("-p", "--project")
    ap.add_argument("-a", "--area")
    ap.add_argument("--date")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--days", type=int)
    ap.add_argument("--group", choices=["date", "company", "project"], default="date")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    start, end = a.start, a.end
    if a.date:
        start = end = a.date
    if a.days:
        start = str(datetime.date.today() - datetime.timedelta(days=a.days - 1))
    rl, rows = rules(), []
    for f in sorted(glob.glob(os.path.join(DIR, "????-??-??.md"))):
        day = os.path.basename(f)[:-3]
        if (start and day < start) or (end and day > end):
            continue
        for ln in open(f, encoding="utf-8"):
            m = LINE.match(ln.rstrip("\n"))
            if not m:
                continue
            t, area, rest = m.groups()
            co, pr, text = tag_of(area, rest, rl)
            if a.company and co != a.company.lower():
                continue
            if a.project and pr != a.project.lower():
                continue
            if a.area and area != a.area:
                continue
            rows.append((day, t, area, co, pr, text))
    if not rows:
        print("no entries")
        return
    if a.summary:
        c = Counter((r[3], r[4] or "-") for r in rows)
        for (co, pr), n in sorted(c.items()):
            print(f"{n:4d}  {co}/{pr}")
        print(f"{len(rows):4d}  total in {len({r[0] for r in rows})} day(s)")
        return
    key = {"date": 0, "company": 3, "project": 4}[a.group]
    groups = defaultdict(list)
    for r in rows:
        groups[r[key] or "-"].append(r)
    for g in sorted(groups):
        print(f"\n## {g}")
        for day, t, area, co, pr, text in groups[g]:
            tag = f"#{co}" + (f"/{pr}" if pr else "")
            print(f"- {day} {t} [{area}] {tag} — {text}" if a.group != "date"
                  else f"- {t} [{area}] {tag} — {text}")


if __name__ == "__main__":
    sys.exit(main())
