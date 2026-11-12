"""Small things shared by the pages."""
from datetime import date, datetime

from nicegui import ui

POSITIONS = ["GK", "CB", "LB", "RB", "DM", "CM", "AM", "LW", "RW", "ST"]


def valid_date(value):
    """True for an empty value or a real YYYY-MM-DD date."""
    if not value:
        return True
    try:
        date.fromisoformat(value)
        return len(value) == 10
    except ValueError:
        return False


DATE_RULE = {"Use YYYY-MM-DD": valid_date}


def valid_time(value):
    """True for an empty value or a time written HH:MM (two digits each)."""
    if not value:
        return True
    try:
        datetime.strptime(value, "%H:%M")
        return len(value) == 5
    except ValueError:
        return False


TIME_RULE = {"Use HH:MM": valid_time}


def to_int(value):
    """Number fields return floats (or None). Convert to int for the database."""
    return int(value) if value not in (None, "") else None


def to_float(value):
    return float(value) if value not in (None, "") else None


def when_label(kickoff):
    """'2026-11-12T18:00' -> '2026-11-12 18:00'. A 00:00 time means 'unknown', so it is hidden."""
    if not kickoff:
        return ""
    day, clock = kickoff[:10], kickoff[11:16]
    return day if clock in ("", "00:00") else f"{day} {clock}"


def match_label(home, away, home_score=None, away_score=None):
    home, away = home or "?", away or "?"
    if home_score is not None and away_score is not None:
        return f"{home} {home_score}–{away_score} {away}"
    return f"{home} – {away}"


def make_confirm(message, on_confirm):
    """A small 'are you sure?' dialog. Returns the dialog; call .open() on it."""
    with ui.dialog() as dialog, ui.card():
        ui.label(message)
        with ui.row():
            ui.button("Cancel", on_click=lambda: dialog.close()).props("flat")
            ui.button("Delete", color="red", on_click=lambda: (dialog.close(), on_confirm()))
    return dialog