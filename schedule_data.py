"""Turns fixtures + players into FullCalendar event dictionaries (no UI code)."""
from datetime import datetime, timedelta

import db
from common import match_label

GREEN = "#16a34a"   # every listed player has a report
AMBER = "#f59e0b"   # a favorite is involved
BLUE = "#3b82f6"    # a watch-list player is involved
GREY = "#6b7280"    # other players only


def build_events(followed_only=True):
    grouped = {}
    for row in db.fixtures_with_players(followed_only):
        grouped.setdefault(row["fixture_id"], []).append(row)

    events = []
    for fixture_id, rows in grouped.items():
        first = rows[0]
        names = ", ".join(r["player_name"] for r in rows)
        title = match_label(first["home"], first["away"], first["home_score"], first["away_score"])

        if all(r["has_report"] for r in rows):
            color = GREEN
        elif any(r["favorite"] for r in rows):
            color = AMBER
        elif any(r["watch_list"] for r in rows):
            color = BLUE
        else:
            color = GREY

        event = {"id": str(fixture_id), "title": f"{title}: {names}", "color": color}
        day, clock = first["kickoff"][:10], first["kickoff"][11:16]
        if clock in ("", "00:00"):          # unknown kick-off time -> all-day event
            event.update(start=day, allDay=True)
        else:
            start = datetime.fromisoformat(first["kickoff"])
            end = start + timedelta(hours=2)
            event.update(start=start.isoformat(timespec="minutes"), end=end.isoformat(timespec="minutes"))
        events.append(event)
    return events