"""The player detail page: info, season stats and transfers."""
import sqlite3
from datetime import date

from nicegui import ui

import db
from common import DATE_RULE, POSITIONS, make_confirm, match_label, to_float, to_int, when_label
from fixture_form import FixtureForm
from player_form import PlayerForm

STAT_NUMBERS = [
    ("matches_played", "Matches"), ("matches_started", "Starts"), ("minutes", "Minutes"),
    ("goals", "Goals"), ("assists", "Assists"),
]
STAT_COLUMNS = [
    {"name": "season", "label": "Season", "field": "season", "align": "left", "sortable": True},
    {"name": "club", "label": "Club", "field": "club", "align": "left"},
    {"name": "mp", "label": "MP", "field": "matches_played"},
    {"name": "st", "label": "Starts", "field": "matches_started"},
    {"name": "min", "label": "Min", "field": "minutes"},
    {"name": "g", "label": "G", "field": "goals"},
    {"name": "a", "label": "A", "field": "assists"},
    {"name": "upd", "label": "Updated", "field": "updated"},
]
REPORT_COLUMNS = [
    {"name": "when", "label": "Date", "field": "when", "align": "left"},
    {"name": "match", "label": "Match", "field": "match", "align": "left"},
    {"name": "pos", "label": "Pos", "field": "position"},
    {"name": "min", "label": "Min", "field": "minutes"},
    {"name": "g", "label": "G", "field": "goals"},
    {"name": "a", "label": "A", "field": "assists"},
    {"name": "ss", "label": "Sofascore", "field": "sofascore_rating"},
    {"name": "my", "label": "My rating", "field": "my_rating"},
]
TRANSFER_COLUMNS = [
    {"name": "date", "label": "Date", "field": "date", "align": "left"},
    {"name": "from", "label": "From", "field": "from_club", "align": "left"},
    {"name": "to", "label": "To", "field": "to_club", "align": "left"},
    {"name": "fee", "label": "Fee", "field": "fee", "align": "right"},
    {"name": "type", "label": "", "field": "type"},
]


def fact(label, value):
    with ui.column().classes("gap-0"):
        ui.label(label).classes("text-xs text-gray-500")
        ui.label(str(value) if value not in (None, "") else "–")


@ui.page("/player/{player_id}")
def player_page(player_id: int):
    if db.player_detail(player_id) is None:
        ui.label("Player not found")
        ui.button("Back to list", on_click=lambda: ui.navigate.to("/"))
        return

    stat = {"id": None}
    transfer = {"id": None}
    report = {"id": None}
    sf, tf, rf = {}, {}, {}

    # ---------- handlers ----------

    def open_stat(stat_id):
        stat["id"] = stat_id
        row = db.get_stat(stat_id) if stat_id else {}
        sf["club_id"].set_options(db.clubs(tracked_only=False))
        stat_title.text = "Edit season stats" if stat_id else "Add season stats"
        sf["season"].value = row.get("season", str(date.today().year))
        # for a new row, default to the player's current club
        default_club = db.get_player(player_id)["current_club_id"]
        sf["club_id"].value = row.get("club_id", default_club)
        for key, _ in STAT_NUMBERS:
            sf[key].value = row.get(key)
        stat_delete.set_visibility(stat_id is not None)
        stat_dialog.open()

    def save_stat():
        season = (sf["season"].value or "").strip()
        if not season:
            ui.notify("Season is required", type="warning")
            return
        data = {key: to_int(sf[key].value) for key, _ in STAT_NUMBERS}
        data.update(season=season, club_id=sf["club_id"].value, updated=date.today().isoformat())
        if stat["id"] is None:
            data["player_id"] = player_id
        try:
            db.save_stat(data, stat["id"])
        except sqlite3.Error as e:
            ui.notify(f"Could not save: {e}", type="negative")
            return
        stat_dialog.close()
        stats_section.refresh()

    def delete_stat():
        db.delete_stat(stat["id"])
        stat_dialog.close()
        stats_section.refresh()

    def open_transfer(transfer_id):
        transfer["id"] = transfer_id
        row = db.get_transfer(transfer_id) if transfer_id else {}
        clubs = db.clubs(tracked_only=False)
        tf["from_club_id"].set_options(clubs)
        tf["to_club_id"].set_options(clubs)
        transfer_title.text = "Edit transfer" if transfer_id else "Add transfer"
        for key, element in tf.items():
            value = row.get(key)
            element.value = bool(value) if key == "is_loan" else value
        transfer_delete.set_visibility(transfer_id is not None)
        transfer_dialog.open()

    def save_transfer():
        if not tf["date"].validate():
            ui.notify("Fix the date first (YYYY-MM-DD)", type="warning")
            return

        def club_or_text(side):
            club_id = tf[f"{side}_club_id"].value
            text = (tf[f"{side}_club_text"].value or "").strip() or None
            return club_id, (None if club_id else text)  # a chosen club wins over free text

        from_id, from_text = club_or_text("from")
        to_id, to_text = club_or_text("to")
        data = {
            "from_club_id": from_id, "from_club_text": from_text,
            "to_club_id": to_id, "to_club_text": to_text,
            "date": tf["date"].value or None,
            "fee_eur": to_int(tf["fee_eur"].value),
            "is_loan": int(bool(tf["is_loan"].value)),
        }
        if transfer["id"] is None:
            data["player_id"] = player_id
        try:
            db.save_transfer(data, transfer["id"])
        except sqlite3.Error as e:
            ui.notify(f"Could not save: {e}", type="negative")
            return
        transfer_dialog.close()
        transfers_section.refresh()

    def delete_transfer():
        db.delete_transfer(transfer["id"])
        transfer_dialog.close()
        transfers_section.refresh()

    def open_report(report_id):
        report["id"] = report_id
        row = db.get_report(report_id) if report_id else {}
        rf["fixture_id"].set_options(db.fixture_options())
        report_title.text = "Edit match report" if report_id else "New match report"
        for key, element in rf.items():
            element.value = row.get(key)
        if not report_id:  # new report: start from the player's usual position
            rf["position"].value = db.get_player(player_id)["position"]
        report_delete.set_visibility(report_id is not None)
        report_dialog.open()

    def after_fixture_saved(fixture_id):
        """The 'New fixture' dialog was used from inside the report form."""
        rf["fixture_id"].set_options(db.fixture_options())
        if fixture_id:
            rf["fixture_id"].value = fixture_id

    def save_report():
        ratings = {k: to_float(rf[k].value) for k in ("sofascore_rating", "my_rating")}
        if any(v is not None and not 1 <= v <= 10 for v in ratings.values()):
            ui.notify("Ratings must be between 1 and 10", type="warning")
            return
        data = {
            "fixture_id": rf["fixture_id"].value,
            "position": rf["position"].value or None,
            "minutes": to_int(rf["minutes"].value),
            "goals": to_int(rf["goals"].value),
            "assists": to_int(rf["assists"].value),
            "comments": (rf["comments"].value or "").strip() or None,
            "key_moments": (rf["key_moments"].value or "").strip() or None,
            **ratings,
        }
        if report["id"] is None:
            data["player_id"] = player_id
        try:
            db.save_report(data, report["id"])
        except sqlite3.Error as e:
            ui.notify(f"Could not save: {e}", type="negative")
            return
        report_dialog.close()
        reports_section.refresh()

    def delete_report():
        db.delete_report(report["id"])
        report_dialog.close()
        reports_section.refresh()

    # ---------- dialogs (built once, filled in when opened) ----------

    form = PlayerForm(on_saved=lambda: info.refresh(), on_deleted=lambda: ui.navigate.to("/"))
    stat_confirm = make_confirm("Delete these season stats?", delete_stat)
    transfer_confirm = make_confirm("Delete this transfer?", delete_transfer)
    report_confirm = make_confirm("Delete this match report?", delete_report)

    with ui.dialog() as stat_dialog, ui.card().classes("w-96"):
        stat_title = ui.label().classes("text-lg font-bold")
        sf["season"] = ui.input("Season (e.g. 2026)").classes("w-full")
        sf["club_id"] = ui.select({}, label="Club", clearable=True, with_input=True).classes("w-full")
        with ui.row():
            for key, label in STAT_NUMBERS:
                sf[key] = ui.number(label, format="%.0f", min=0).classes("w-36")
        with ui.row().classes("w-full justify-between"):
            stat_delete = ui.button("Delete", color="red", on_click=lambda: stat_confirm.open()).props("flat")
            with ui.row():
                ui.button("Cancel", on_click=lambda: stat_dialog.close()).props("flat")
                ui.button("Save", on_click=save_stat)

    with ui.dialog() as transfer_dialog, ui.card().classes("w-96"):
        transfer_title = ui.label().classes("text-lg font-bold")
        tf["date"] = ui.input("Date (YYYY-MM-DD)", validation=DATE_RULE).classes("w-full")
        tf["from_club_id"] = ui.select({}, label="From club", clearable=True, with_input=True).classes("w-full")
        tf["from_club_text"] = ui.input("…or club not in the database").classes("w-full")
        tf["to_club_id"] = ui.select({}, label="To club", clearable=True, with_input=True).classes("w-full")
        tf["to_club_text"] = ui.input("…or club not in the database").classes("w-full")
        tf["fee_eur"] = ui.number("Fee (€, 0 = free)", format="%.0f", min=0).classes("w-full")
        tf["is_loan"] = ui.checkbox("Loan")
        with ui.row().classes("w-full justify-between"):
            transfer_delete = ui.button("Delete", color="red", on_click=lambda: transfer_confirm.open()).props("flat")
            with ui.row():
                ui.button("Cancel", on_click=lambda: transfer_dialog.close()).props("flat")
                ui.button("Save", on_click=save_transfer)

    with ui.dialog() as report_dialog, ui.card().classes("w-[36rem]"):
        report_title = ui.label().classes("text-lg font-bold")
        with ui.row().classes("w-full items-center no-wrap"):
            rf["fixture_id"] = ui.select({}, label="Match", clearable=True, with_input=True).classes("grow")
            ui.button("New match", icon="add", on_click=lambda: fixture_form.open(None)).props("flat")
        rf["position"] = ui.select(POSITIONS, label="Position played", clearable=True).classes("w-full")
        with ui.row():
            rf["minutes"] = ui.number("Minutes", format="%.0f", min=0, max=130).classes("w-28")
            rf["goals"] = ui.number("Goals", format="%.0f", min=0).classes("w-28")
            rf["assists"] = ui.number("Assists", format="%.0f", min=0).classes("w-28")
        with ui.row():
            rf["sofascore_rating"] = ui.number("Sofascore rating", format="%.1f", min=1, max=10, step=0.1).classes("w-40")
            rf["my_rating"] = ui.number("My rating", format="%.1f", min=1, max=10, step=0.1).classes("w-40")
        rf["comments"] = ui.textarea("Comments").classes("w-full")
        rf["key_moments"] = ui.textarea("Key moments").classes("w-full")
        with ui.row().classes("w-full justify-between"):
            report_delete = ui.button("Delete", color="red", on_click=lambda: report_confirm.open()).props("flat")
            with ui.row():
                ui.button("Cancel", on_click=lambda: report_dialog.close()).props("flat")
                ui.button("Save", on_click=save_report)

    fixture_form = FixtureForm(on_saved=after_fixture_saved)

    # ---------- page sections (refreshable = can be redrawn after a change) ----------

    @ui.refreshable
    def info():
        p = db.player_detail(player_id)
        with ui.row().classes("w-full items-center"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round")
            ui.label(p["name"]).classes("text-2xl font-bold")
            if p["favorite"]:
                ui.badge("Favorite", color="amber")
            if p["watch_list"]:
                ui.badge("Watch list", color="blue")
            if p["homegrown_sweden"]:
                ui.badge("Homegrown", color="green")
            if p["linked_with_aik"]:
                ui.badge("Linked with AIK", color="grey")
            ui.space()
            ui.button("Edit", icon="edit", on_click=lambda: form.open(player_id))
        with ui.card().classes("w-full"):
            with ui.row().classes("gap-8"):
                fact("Position", p["position"])
                fact("Age", p["age"])
                fact("Born", p["dob"])
                fact("Nationality", p["nation"])
                fact("Club", p["club"])
                fact("Contract", p["contract_expiry"])
                fact("Value", f"€{p['market_value_eur']:,}" if p["market_value_eur"] else None)
            if p["transfermarkt_url"]:
                ui.link("Transfermarkt", p["transfermarkt_url"], new_tab=True)
            if p["comments"]:
                ui.separator()
                ui.label(p["comments"]).classes("whitespace-pre-wrap")

    @ui.refreshable
    def stats_section():
        with ui.row().classes("w-full items-center"):
            ui.label("Season stats").classes("text-lg font-bold")
            ui.space()
            ui.button("Add", icon="add", on_click=lambda: open_stat(None))
        rows = db.season_stats_for(player_id)
        if not rows:
            ui.label("No stats yet.").classes("text-gray-500")
            return
        table = ui.table(columns=STAT_COLUMNS, rows=rows, row_key="id").classes("w-full cursor-pointer")
        table.on("rowClick", lambda e: open_stat(e.args[1]["id"]))

    @ui.refreshable
    def reports_section():
        with ui.row().classes("w-full items-center"):
            ui.label("Match reports").classes("text-lg font-bold")
            ui.space()
            ui.button("Add", icon="add", on_click=lambda: open_report(None))
        rows = db.reports_for(player_id)
        if not rows:
            ui.label("No reports yet.").classes("text-gray-500")
            return
        for r in rows:
            r["when"] = when_label(r["kickoff"])
            r["match"] = match_label(r["home"], r["away"], r["home_score"], r["away_score"]) if r["fixture_id"] else "–"
        table = ui.table(columns=REPORT_COLUMNS, rows=rows, row_key="id").classes("w-full cursor-pointer")
        table.on("rowClick", lambda e: open_report(e.args[1]["id"]))

    @ui.refreshable
    def transfers_section():
        with ui.row().classes("w-full items-center"):
            ui.label("Transfers").classes("text-lg font-bold")
            ui.space()
            ui.button("Add", icon="add", on_click=lambda: open_transfer(None))
        rows = db.transfers_for(player_id)
        if not rows:
            ui.label("No transfers yet.").classes("text-gray-500")
            return
        for r in rows:
            fee = r["fee_eur"]
            r["fee"] = "–" if fee is None else ("Free" if fee == 0 else f"€{fee:,}")
            r["type"] = "Loan" if r["is_loan"] else ""
        table = ui.table(columns=TRANSFER_COLUMNS, rows=rows, row_key="id").classes("w-full cursor-pointer")
        table.on("rowClick", lambda e: open_transfer(e.args[1]["id"]))

    # ---------- layout ----------

    info()
    stats_section()
    reports_section()
    transfers_section()