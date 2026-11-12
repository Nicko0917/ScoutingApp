"""The add/edit player dialog, shared by the list page and the detail page."""
import sqlite3

from nicegui import ui

import db
from common import DATE_RULE, POSITIONS, make_confirm, to_int

FLAGS = ["favorite", "watch_list", "homegrown_sweden", "linked_with_aik"]
DATE_FIELDS = ["dob", "contract_expiry"]


class PlayerForm:
    def __init__(self, on_saved, on_deleted):
        """Call this while building a page. on_saved / on_deleted run after those actions."""
        self.on_saved = on_saved
        self.on_deleted = on_deleted
        self.player_id = None
        self.f = f = {}

        with ui.dialog() as self.dialog, ui.card().classes("w-[34rem]"):
            self.title = ui.label().classes("text-lg font-bold")
            f["name"] = ui.input("Name").classes("w-full")
            f["position"] = ui.select(POSITIONS, label="Position", clearable=True).classes("w-full")
            f["dob"] = ui.input("Date of birth (YYYY-MM-DD)", validation=DATE_RULE).classes("w-full")
            f["nationality_id"] = ui.select({}, label="Nationality", clearable=True, with_input=True).classes("w-full")
            f["current_club_id"] = ui.select({}, label="Current club", clearable=True, with_input=True).classes("w-full")
            f["contract_expiry"] = ui.input("Contract expiry (YYYY-MM-DD)", validation=DATE_RULE).classes("w-full")
            f["market_value_eur"] = ui.number("Market value (€)", format="%.0f", min=0).classes("w-full")
            f["transfermarkt_url"] = ui.input("Transfermarkt URL").classes("w-full")
            with ui.row():
                f["favorite"] = ui.checkbox("Favorite")
                f["watch_list"] = ui.checkbox("Watch list")
                f["homegrown_sweden"] = ui.checkbox("Homegrown in Sweden")
                f["linked_with_aik"] = ui.checkbox("Linked with AIK")
            f["comments"] = ui.textarea("Comments").classes("w-full")
            with ui.row().classes("w-full justify-between"):
                self.delete_button = ui.button("Delete", color="red", on_click=lambda: self.confirm.open()).props("flat")
                with ui.row():
                    ui.button("Cancel", on_click=lambda: self.dialog.close()).props("flat")
                    ui.button("Save", on_click=self.save)

        self.confirm = make_confirm("Delete this player and all their stats, transfers and reports?", self.delete)

    def open(self, player_id=None):
        f = self.f
        # Refresh dropdown options every time, so new clubs from the Setup tab show up
        f["nationality_id"].set_options(db.nations())
        f["current_club_id"].set_options(db.clubs())
        self.player_id = player_id
        data = db.get_player(player_id) if player_id else {}
        self.title.text = "Edit player" if player_id else "New player"
        for key, element in f.items():
            value = data.get(key)
            element.value = bool(value) if key in FLAGS else value
        self.delete_button.set_visibility(player_id is not None)
        self.dialog.open()

    def save(self):
        f = self.f
        name = (f["name"].value or "").strip()
        if not name:
            ui.notify("Name is required", type="warning")
            return
        if not all([f[k].validate() for k in DATE_FIELDS]):
            ui.notify("Fix the dates first (YYYY-MM-DD)", type="warning")
            return
        data = {key: element.value for key, element in f.items()}
        data["name"] = name
        for key in FLAGS:
            data[key] = int(bool(data[key]))
        data["market_value_eur"] = to_int(data["market_value_eur"])
        for key in ["dob", "contract_expiry", "position", "transfermarkt_url", "comments"]:
            data[key] = data[key] or None
        try:
            db.save_player(data, self.player_id)
        except sqlite3.Error as e:
            ui.notify(f"Could not save: {e}", type="negative")
            return
        self.dialog.close()
        self.on_saved()
        ui.notify("Saved", type="positive")

    def delete(self):
        db.delete_player(self.player_id)
        self.dialog.close()
        self.on_deleted()
        ui.notify("Player deleted")