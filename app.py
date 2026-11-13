"""Scouting app. Run: python app.py  (then it opens in your browser)"""
from pathlib import Path

from nicegui import ui

import db
import player_page  # noqa: F401  (importing it registers the /player/<id> page)
import schedule_data
from common import POSITIONS, match_label, when_label
from fixture_form import FixtureForm
from fullcalendar import FullCalendar
from player_form import PlayerForm

IMAGES = Path(__file__).parent / "images"

# FullCalendar's JavaScript lives in lib/ (copied from NiceGUI's examples/fullcalendar)
CALENDAR_LIB = Path(__file__).parent / "lib" / "index.global.min.js"
CALENDAR_OPTIONS = {
    "initialView": "dayGridMonth",
    "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listWeek,listMonth"},
    "views": {
        "dayGridMonth": {"buttonText": "Month"},
        "listWeek": {"buttonText": "Week list"},
        "listMonth": {"buttonText": "Month list"},
    },
    "firstDay": 1,                       # weeks start on Monday
    "weekNumbers": True,
    "timeZone": "local",                 # show kick-off times exactly as stored
    "height": "auto",
    "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    "displayEventEnd": False,
    "noEventsContent": "No fixtures with your players",
}


@ui.page("/")
def index():
    # ---------- handlers ----------

    def refresh():
        rows = db.list_players(
            search=search.value or "",
            position=position_filter.value,
            only_favorites=fav_filter.value,
            only_watch=watch_filter.value,
        )
        for r in rows:
            photo_path = r.get("photo_path")
            if photo_path:
                photo_url = "/" + photo_path.replace("\\", "/").lstrip("/")
                r["photo"] = photo_url
            else:
                r["photo"] = f"/images/{r['id']}.png" if (IMAGES / f"{r['id']}.png").exists() else ""
            r["flags"] = ("★" if r["favorite"] else "") + ("◉" if r["watch_list"] else "")
        table.rows = rows
        table.update()
        count_label.text = f"{len(rows)} players"

    def refresh_fixtures():
        rows = db.fixtures_list()
        for r in rows:
            r["when"] = when_label(r["kickoff"])
            has_score = r["home_score"] is not None and r["away_score"] is not None
            r["score"] = f"{r['home_score']}–{r['away_score']}" if has_score else ""
        fixture_table.rows = rows
        fixture_table.update()

    def refresh_schedule():
        if calendar is None:
            return
        calendar.events.clear()
        calendar.events.extend(schedule_data.build_events(scope.value == "followed"))
        calendar.update()

    def open_fixture_info(e):
        """A calendar event was clicked: show the match and the players involved."""
        fixture_id = int(e.args["id"])
        fixture = db.fixture_detail(fixture_id)
        if fixture is None:
            return
        current["id"] = fixture_id
        info_title.text = match_label(fixture["home"], fixture["away"], fixture["home_score"], fixture["away_score"])
        info_meta.text = " · ".join(x for x in [when_label(fixture["kickoff"]), fixture["competition"]] if x)
        info_players.clear()
        with info_players:
            players = db.players_for_fixture(fixture_id)
            if not players:
                ui.label("None of your players are at these clubs.").classes("text-gray-500")
            for p in players:
                with ui.row().classes("w-full items-center no-wrap"):
                    ui.label(("★ " if p["favorite"] else "") + p["name"]).classes("grow")
                    ui.button("Profile", on_click=lambda pid=p["id"]: ui.navigate.to(f"/player/{pid}")).props("flat dense")
                    if p["has_report"]:
                        ui.label("✓ report")
                    else:
                        ui.button(
                            "Write report",
                            on_click=lambda pid=p["id"]: ui.navigate.to(f"/player/{pid}?report_fixture={fixture_id}"),
                        ).props("dense")
        info_dialog.open()

    def reload_options():
        league_nation.set_options(db.nations())
        club_league.set_options(db.leagues())
        club_table.rows = db.clubs_detail()
        club_table.update()

    def add_nation():
        if not ((nation_name.value) or "").strip():
            return
        db.add_nation(nation_name.value.strip(), (nation_abbr.value or "").strip())
        nation_name.value = nation_abbr.value = ""
        reload_options()
        ui.notify("Nation added")

    def add_league():
        if not ((league_name.value) or "").strip():
            return
        tier = league_tier.value
        db.add_league(league_name.value.strip(), league_nation.value, int(tier) if tier else None)
        league_name.value = ""
        reload_options()
        ui.notify("League added")

    def add_club():
        if not ((club_name.value) or "").strip():
            return
        db.add_club(club_name.value.strip(), club_league.value)
        club_name.value = ""
        reload_options()
        ui.notify("Club added")

    # ---------- layout ----------

    calendar = None   # becomes the calendar element below, if its library is installed
    current = {"id": None}

    form = PlayerForm(on_saved=lambda: (refresh(), refresh_schedule()),
                      on_deleted=lambda: (refresh(), refresh_schedule()))
    fixture_form = FixtureForm(on_saved=lambda fixture_id: (refresh_fixtures(), refresh_schedule()))

    with ui.dialog() as info_dialog, ui.card().classes("w-[32rem]"):
        info_title = ui.label().classes("text-lg font-bold")
        info_meta = ui.label().classes("text-gray-500")
        info_players = ui.column().classes("w-full")
        with ui.row().classes("w-full justify-between"):
            ui.button("Edit fixture", on_click=lambda: (info_dialog.close(), fixture_form.open(current["id"]))).props("flat")
            ui.button("Close", on_click=lambda: info_dialog.close()).props("flat")

    with ui.tabs().classes("w-full") as tabs:
        players_tab = ui.tab("Players")
        schedule_tab = ui.tab("Schedule")
        fixtures_tab = ui.tab("Fixtures")
        setup_tab = ui.tab("Setup")

    with ui.tab_panels(tabs, value=players_tab).classes("w-full"):

        with ui.tab_panel(players_tab):
            with ui.row().classes("w-full items-center"):
                search = ui.input("Search name", on_change=refresh).props("clearable")
                position_filter = ui.select(POSITIONS, label="Position", clearable=True, on_change=refresh).classes("w-32")
                fav_filter = ui.checkbox("Favorites", on_change=refresh)
                watch_filter = ui.checkbox("Watch list", on_change=refresh)
                count_label = ui.label().classes("text-gray-500")
                ui.space()
                ui.button("New player", icon="add", on_click=lambda: form.open(None))

            columns = [
                {"name": "photo", "label": "", "field": "photo", "sortable": False},
                {"name": "name", "label": "Name", "field": "name", "align": "left", "sortable": True},
                {"name": "flags", "label": "", "field": "flags"},
                {"name": "position", "label": "Pos", "field": "position", "sortable": True},
                {"name": "age", "label": "Age", "field": "age", "sortable": True},
                {"name": "nation", "label": "Nation", "field": "nation", "sortable": True},
                {"name": "club", "label": "Club", "field": "club", "align": "left", "sortable": True},
                {"name": "contract", "label": "Contract", "field": "contract_expiry", "sortable": True},
                {"name": "value", "label": "Value (M€)", "field": "value_m", "sortable": True},
            ]
            table = ui.table(columns=columns, rows=[], row_key="id", pagination=25).classes("w-full cursor-pointer")
            table.add_slot("body-cell-photo", r'''
                <q-td :props="props">
                    <q-avatar size="40px" color="grey-3">
                        <q-img v-if="props.value" :src="props.value" fit="cover" />
                        <q-icon v-else name="person" color="grey-6" />
                    </q-avatar>
                </q-td>
            ''')
            # clicking a row opens that player's detail page
            table.on("rowClick", lambda e: ui.navigate.to(f"/player/{e.args[1]['id']}"))

        with ui.tab_panel(schedule_tab):
            if not CALENDAR_LIB.exists():
                ui.label(
                    "The calendar library is missing. Copy the 'lib' folder from NiceGUI's "
                    "examples/fullcalendar into this folder (next to app.py), then restart."
                ).classes("text-orange-700")
            else:
                with ui.row().classes("items-center gap-6"):
                    scope = ui.toggle(
                        {"followed": "Favorites & watch list", "all": "All players"},
                        value="followed", on_change=refresh_schedule,
                    )
                    ui.label("● report written").style("color: #16a34a")
                    ui.label("● favorite").style("color: #f59e0b")
                    ui.label("● watch list").style("color: #3b82f6")
                    ui.label("● other").style("color: #6b7280")
                options = {**CALENDAR_OPTIONS, "events": schedule_data.build_events(True)}
                calendar = FullCalendar(options, on_click=open_fixture_info)

        with ui.tab_panel(fixtures_tab):
            with ui.row().classes("w-full items-center"):
                ui.label("Matches you have watched or want to write reports on.").classes("text-gray-500")
                ui.space()
                ui.button("New fixture", icon="add", on_click=lambda: fixture_form.open(None))
            fixture_table = ui.table(
                columns=[
                    {"name": "when", "label": "Date", "field": "when", "align": "left", "sortable": True},
                    {"name": "home", "label": "Home", "field": "home", "align": "left", "sortable": True},
                    {"name": "score", "label": "Score", "field": "score"},
                    {"name": "away", "label": "Away", "field": "away", "align": "left", "sortable": True},
                    {"name": "comp", "label": "Competition", "field": "competition", "align": "left"},
                    {"name": "reports", "label": "Reports", "field": "report_count", "sortable": True},
                ],
                rows=[], row_key="id", pagination=25,
            ).classes("w-full cursor-pointer")
            fixture_table.on("rowClick", lambda e: fixture_form.open(e.args[1]["id"]))

        with ui.tab_panel(setup_tab):
            ui.label("Add the nations, leagues and clubs you want to pick from in the player form.").classes("text-gray-500")

            ui.label("Nation").classes("text-lg font-bold mt-4")
            with ui.row().classes("items-center"):
                nation_name = ui.input("Name")
                nation_abbr = ui.input("Abbreviation").classes("w-32")
                ui.button("Add", on_click=add_nation)

            ui.label("League").classes("text-lg font-bold mt-4")
            with ui.row().classes("items-center"):
                league_name = ui.input("Name")
                league_nation = ui.select({}, label="Nation", clearable=True).classes("w-48")
                league_tier = ui.number("Tier", format="%.0f", min=1).classes("w-24")
                ui.button("Add", on_click=add_league)

            ui.label("Club").classes("text-lg font-bold mt-4")
            with ui.row().classes("items-center"):
                club_name = ui.input("Name")
                club_league = ui.select({}, label="League", clearable=True).classes("w-48")
                ui.button("Add", on_click=add_club)

            club_table = ui.table(
                columns=[
                    {"name": "name", "label": "Club", "field": "name", "align": "left", "sortable": True},
                    {"name": "league", "label": "League", "field": "league", "align": "left", "sortable": True},
                ],
                rows=[], row_key="id", pagination=15,
            ).classes("w-full mt-4")

    reload_options()
    refresh()
    refresh_fixtures()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Scouting", reload=False)  # native=True opens its own window (pip install pywebview)
