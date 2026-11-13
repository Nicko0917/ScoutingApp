#!/usr/bin/env python3
"""Import a FotMob .ics calendar into the existing `fixture` / `club` tables.

Usage:  python import_ics.py Västerås_SK.ics fixtures.db [--tz Europe/Stockholm]

- Clubs are matched by name (case-insensitive). If a club isn't in `club`,
  it is created with tracked = 0 and just its name.
- Re-running is safe: fixtures are upserted on ics_uid, updating club links,
  kickoff, competition and scores (sofascore_url, which here holds the FotMob match URL, is only filled
  in when empty, so values you set by hand are kept). Club links
  are re-resolved each run, so a club you add later (tracked = 1) takes over
  from the auto-created one. --prune then deletes auto-created clubs that no
  fixture uses any more.
- kickoff is stored as 'YYYY-MM-DDTHH:MM' (UTC unless --tz is given).
"""
import argparse
import re
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def unfold(text):
    """RFC 5545: a line starting with space/tab continues the previous line."""
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def unescape(value):
    return (value.replace("\\n", "\n").replace("\\N", "\n")
                 .replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\"))


def parse_events(path):
    with open(path, encoding="utf-8") as f:
        lines = unfold(f.read())
    events, current, alarm_depth = [], None, 0
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            events.append(current)
            current = None
        elif line == "BEGIN:VALARM":
            alarm_depth += 1                  # skip reminder properties
        elif line == "END:VALARM":
            alarm_depth -= 1
        elif current is not None and alarm_depth == 0 and ":" in line:
            name, value = line.split(":", 1)
            current[name.split(";")[0]] = unescape(value)
    return events


def kickoff_str(dtstart, tz):
    dt = datetime.strptime(dtstart, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%Y-%m-%dT%H:%M")


def get_or_create_club(conn, name):
    row = conn.execute(
        "SELECT id FROM club WHERE name = ? COLLATE NOCASE "
        "ORDER BY tracked DESC, id LIMIT 1", (name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO club (name, tracked) VALUES (?, 0)", (name,))
    return cur.lastrowid


def import_events(conn, events, tz):
    new_clubs_before = conn.execute("SELECT count(*) FROM club").fetchone()[0]
    skipped = []
    for ev in events:
        summary = ev.get("SUMMARY", "").replace("⚽️", "").replace("⚽", "").strip()
        # "Home - Away  (2-1)"; score only present once played
        m = re.match(r"^(.*?)\s+-\s+(.*?)\s*(?:\((\d+)-(\d+)\))?$", summary)
        if not m:
            skipped.append(summary)
            continue
        home, away, hs, as_ = m.groups()
        desc = ev.get("DESCRIPTION", "").split("\n")
        competition = desc[1] if len(desc) > 1 else None

        conn.execute("""
            INSERT INTO fixture (ics_uid, home_club_id, away_club_id, kickoff,
                                 competition, home_score, away_score, sofascore_url)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(ics_uid) DO UPDATE SET
                home_club_id=excluded.home_club_id,
                away_club_id=excluded.away_club_id,
                kickoff=excluded.kickoff, competition=excluded.competition,
                home_score=excluded.home_score, away_score=excluded.away_score,
                sofascore_url=COALESCE(fixture.sofascore_url, excluded.sofascore_url)
        """, (
            ev["UID"],
            get_or_create_club(conn, home),
            get_or_create_club(conn, away),
            kickoff_str(ev["DTSTART"], tz),
            competition,
            int(hs) if hs is not None else None,
            int(as_) if as_ is not None else None,
            ev.get("URL"),
        ))
    created = conn.execute("SELECT count(*) FROM club").fetchone()[0] - new_clubs_before
    return len(events) - len(skipped), created, skipped


def prune_orphans(conn):
    """Delete auto-created clubs (tracked = 0) that no fixture references."""
    return conn.execute("""
        DELETE FROM club WHERE tracked = 0
          AND id NOT IN (SELECT home_club_id FROM fixture WHERE home_club_id IS NOT NULL)
          AND id NOT IN (SELECT away_club_id FROM fixture WHERE away_club_id IS NOT NULL)
    """).rowcount


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ics")
    ap.add_argument("db")
    ap.add_argument("--prune", action="store_true",
                    help="delete unused auto-created clubs afterwards")
    ap.add_argument("--tz", default="Europe/Stockholm", help="store kickoff in this zone")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    with conn:   # one transaction: all or nothing
        n, created, skipped = import_events(conn, parse_events(args.ics),
                                            ZoneInfo(args.tz))
    print(f"Imported {n} fixtures, created {created} new clubs (tracked=0).")
    if args.prune:
        with conn:
            print(f"Pruned {prune_orphans(conn)} unused auto-created clubs.")
    for s in skipped:
        print("Skipped (couldn't parse teams):", s)