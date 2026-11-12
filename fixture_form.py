"""The add/edit fixture dialog, used on the Fixtures tab and inside the report form."""
import sqlite3
from datetime import date

from nicegui import ui

import db
from common import DATE_RULE, TIME_RULE, make_confirm, to_int


class FixtureForm:
    def __init__(self, on_saved):
        """on_saved(fixture_id) runs after saving; it gets None after a delete."""
        self.on_saved = on_saved
        self.fixture_id = None
        self.f = f = {}

        with ui.dialog() as self.dialog, ui.card().classes("w-[32rem]"):
            self.title = ui.label().classes("text-lg font-bold")
            f["home_club_id"] = ui.select({}, label="Home club", clearable=True, with_input=True).classes("w-full")
            f["home_new"] = ui.input("…or new club").classes("w-full")
            f["away_club_id"] = ui.select({}, label="Away club", clearable=True, with_input=True).classes("w-full")
            f["away_new"] = ui.input("…or new club").classes("w-full")
            with ui.row().classes("w-full"):
                f["date"] = ui.input("Date (YYYY-MM-DD)", validation=DATE_RULE).classes("w-48")
                f["time"] = ui.input("Kick-off (HH:MM, optional)", validation=TIME_RULE).classes("w-48")
            f["competition"] = ui.input("Competition").classes("w-full")
            with ui.row():
                f["home_score"] = ui.number("Home goals", format="%.0f", min=0).classes("w-36")
                f["away_score"] = ui.number("Away goals", format="%.0f", min=0).classes("w-36")
            f["sofascore_url"] = ui.input("Sofascore link").classes("w-full")
            with ui.row().classes("w-full justify-between"):
                self.delete_button = ui.button("Delete", color="red", on_click=lambda: self.confirm.open()).props("flat")
                with ui.row():
                    ui.button("Cancel", on_click=lambda: self.dialog.close()).props("flat")
                    ui.button("Save", on_click=self.save)

        self.confirm = make_confirm("Delete this fixture?", self.delete)

    def open(self, fixture_id=None):
        f = self.f
        clubs = db.clubs(tracked_only=False)  # opponents may be untracked clubs
        f["home_club_id"].set_options(clubs)
        f["away_club_id"].set_options(clubs)
        self.fixture_id = fixture_id
        row = db.get_fixture(fixture_id) if fixture_id else {}
        self.title.text = "Edit fixture" if fixture_id else "New fixture"
        kickoff = row.get("kickoff") or ""
        clock = kickoff[11:16]
        f["home_club_id"].value = row.get("home_club_id")
        f["away_club_id"].value = row.get("away_club_id")
        f["home_new"].value = ""
        f["away_new"].value = ""
        f["date"].value = kickoff[:10] if fixture_id else date.today().isoformat()
        f["time"].value = clock if clock not in ("", "00:00") else None
        for key in ["competition", "home_score", "away_score", "sofascore_url"]:
            f[key].value = row.get(key)
        self.delete_button.set_visibility(fixture_id is not None)
        self.dialog.open()

    def _club(self, side):
        """Chosen club id, or create/find a club from the typed name. None if neither."""
        club_id = self.f[f"{side}_club_id"].value
        if club_id:
            return club_id
        name = (self.f[f"{side}_new"].value or "").strip()
        return db.get_or_create_club(name) if name else None

    def _has_club(self, side):
        return bool(self.f[f"{side}_club_id"].value or (self.f[f"{side}_new"].value or "").strip())

    def save(self):
        f = self.f
        if not (self._has_club("home") and self._has_club("away")):
            ui.notify("Pick or type both clubs", type="warning")
            return
        day = (f["date"].value or "").strip()
        if not day or not all([f["date"].validate(), f["time"].validate()]):
            ui.notify("Enter a valid date (YYYY-MM-DD) and time (HH:MM)", type="warning")
            return
        home_score, away_score = to_int(f["home_score"].value), to_int(f["away_score"].value)
        if (home_score is None) != (away_score is None):
            ui.notify("Fill in both scores, or leave both empty", type="warning")
            return
        home, away = self._club("home"), self._club("away")
        if home == away:
            ui.notify("Home and away can't be the same club", type="warning")
            return
        data = {
            "home_club_id": home,
            "away_club_id": away,
            "kickoff": f"{day}T{(f['time'].value or '').strip() or '00:00'}",
            "competition": (f["competition"].value or "").strip() or None,
            "home_score": home_score,
            "away_score": away_score,
            "sofascore_url": (f["sofascore_url"].value or "").strip() or None,
        }
        try:
            fixture_id = db.save_fixture(data, self.fixture_id)
        except sqlite3.Error as e:
            ui.notify(f"Could not save: {e}", type="negative")
            return
        self.dialog.close()
        self.on_saved(fixture_id)
        ui.notify("Fixture saved", type="positive")

    def delete(self):
        n = db.fixture_report_count(self.fixture_id)
        if n:
            ui.notify(f"This fixture has {n} report(s). Delete those first.", type="warning")
            return
        try:
            db.delete_fixture(self.fixture_id)
        except sqlite3.Error as e:
            ui.notify(f"Could not delete: {e}", type="negative")
            return
        self.dialog.close()
        self.on_saved(None)
        ui.notify("Fixture deleted")