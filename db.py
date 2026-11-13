"""All database queries live here, so the UI code never contains SQL."""
import unicodedata

from create_db import connect

PLAYER_FIELDS = [
    "name", "dob", "position", "nationality_id", "current_club_id",
    "transfermarkt_url", "contract_expiry", "market_value_eur",
    "homegrown_sweden", "linked_with_aik", "favorite", "watch_list", "comments", "photo_path",
]
STAT_FIELDS = [
    "player_id", "season", "club_id", "matches_played", "matches_started",
    "minutes", "goals", "assists", "updated",
]
TRANSFER_FIELDS = [
    "player_id", "from_club_id", "from_club_text", "to_club_id", "to_club_text",
    "date", "fee_eur", "is_loan",
]

FIXTURE_FIELDS = [
    "ics_uid", "home_club_id", "away_club_id", "kickoff", "competition",
    "home_score", "away_score", "sofascore_url",
]
REPORT_FIELDS = [
    "player_id", "fixture_id", "position", "minutes", "goals", "assists",
    "sofascore_rating", "my_rating", "comments", "key_moments",
]

AGE_SQL = """CASE WHEN p.dob IS NULL THEN NULL
                ELSE CAST((julianday('now') - julianday(p.dob)) / 365.25 AS INTEGER) END"""


# ---------- small helpers ----------

def query(sql, args=()):
    conn = connect()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def execute(sql, args=()):
    """Run a write. Commits on success, rolls back if it raises."""
    conn = connect()
    try:
        with conn:
            return conn.execute(sql, args).lastrowid
    finally:
        conn.close()


def _one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None


def _save(table, allowed, data, row_id=None):
    """Insert (row_id None) or update. Only whitelisted columns are written."""
    cols = [c for c in allowed if c in data]
    values = [data[c] for c in cols]
    if row_id is None:
        marks = ", ".join(["?"] * len(cols))
        return execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({marks})", values)
    sets = ", ".join(f"{c} = ?" for c in cols)
    execute(f"UPDATE {table} SET {sets} WHERE id = ?", values + [row_id])
    return row_id


def _norm(text):
    """Lowercase and strip accents, so 'ostlund' finds 'Östlund'."""
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


# ---------- players ----------

def list_players(search="", position=None, only_favorites=False, only_watch=False):
    rows = query(
        f"""
        SELECT p.id, p.name, p.position,
               COALESCE(n.abbreviation, n.name) AS nation,
               c.name AS club,
               {AGE_SQL} AS age,
               p.contract_expiry,
               ROUND(p.market_value_eur / 1000000.0, 2) AS value_m,
               p.favorite, p.watch_list, p.photo_path
        FROM player p
        LEFT JOIN nation n ON n.id = p.nationality_id
        LEFT JOIN club c ON c.id = p.current_club_id
        WHERE (:position IS NULL OR p.position = :position)
          AND (:fav = 0 OR p.favorite = 1)
          AND (:watch = 0 OR p.watch_list = 1)
        ORDER BY p.name COLLATE NOCASE
        """,
        {"position": position, "fav": int(bool(only_favorites)), "watch": int(bool(only_watch))},
    )
    if search:
        needle = _norm(search.strip())
        rows = [r for r in rows if needle in _norm(r["name"])]
    return rows


def get_player(player_id):
    return _one("SELECT * FROM player WHERE id = ?", (player_id,))


def player_detail(player_id):
    """The player row plus readable nation/club names and age."""
    return _one(
        f"""SELECT p.*, n.name AS nation, c.name AS club, {AGE_SQL} AS age
            FROM player p
            LEFT JOIN nation n ON n.id = p.nationality_id
            LEFT JOIN club c ON c.id = p.current_club_id
            WHERE p.id = ?""",
        (player_id,),
    )


def save_player(data, player_id=None):
    return _save("player", PLAYER_FIELDS, data, player_id)


def delete_player(player_id):
    """Also removes the player's stats, transfers and reports (ON DELETE CASCADE)."""
    execute("DELETE FROM player WHERE id = ?", (player_id,))


# ---------- season stats ----------

def season_stats_for(player_id):
    return query(
        """SELECT s.*, c.name AS club
           FROM season_stats s LEFT JOIN club c ON c.id = s.club_id
           WHERE s.player_id = ? ORDER BY s.season DESC, s.id DESC""",
        (player_id,),
    )


def get_stat(stat_id):
    return _one("SELECT * FROM season_stats WHERE id = ?", (stat_id,))


def save_stat(data, stat_id=None):
    return _save("season_stats", STAT_FIELDS, data, stat_id)


def delete_stat(stat_id):
    execute("DELETE FROM season_stats WHERE id = ?", (stat_id,))


# ---------- transfers ----------

def transfers_for(player_id):
    return query(
        """SELECT t.id, t.date,
                  COALESCE(fc.name, t.from_club_text) AS from_club,
                  COALESCE(tc.name, t.to_club_text) AS to_club,
                  t.fee_eur, t.is_loan
           FROM transfer t
           LEFT JOIN club fc ON fc.id = t.from_club_id
           LEFT JOIN club tc ON tc.id = t.to_club_id
           WHERE t.player_id = ? ORDER BY t.date DESC, t.id DESC""",
        (player_id,),
    )


def get_transfer(transfer_id):
    return _one("SELECT * FROM transfer WHERE id = ?", (transfer_id,))


def save_transfer(data, transfer_id=None):
    return _save("transfer", TRANSFER_FIELDS, data, transfer_id)


def delete_transfer(transfer_id):
    execute("DELETE FROM transfer WHERE id = ?", (transfer_id,))


# ---------- lookup tables (nations, leagues, clubs) ----------

def nations():
    return {r["id"]: r["name"] for r in query("SELECT id, name FROM nation ORDER BY name COLLATE NOCASE")}


def leagues():
    return {r["id"]: r["name"] for r in query("SELECT id, name FROM league ORDER BY name COLLATE NOCASE")}


def clubs(tracked_only=True):
    where = "WHERE tracked = 1" if tracked_only else ""
    return {r["id"]: r["name"] for r in query(f"SELECT id, name FROM club {where} ORDER BY name COLLATE NOCASE")}


def clubs_detail():
    return query(
        """SELECT c.id, c.name, l.name AS league
           FROM club c LEFT JOIN league l ON l.id = c.league_id
           WHERE c.tracked = 1 ORDER BY c.name COLLATE NOCASE"""
    )


def add_nation(name, abbreviation=None):
    return execute("INSERT INTO nation (name, abbreviation) VALUES (?, ?)", (name, abbreviation or None))


def add_league(name, nation_id=None, tier=None):
    return execute("INSERT INTO league (name, nation_id, tier) VALUES (?, ?, ?)", (name, nation_id, tier))


def add_club(name, league_id=None, tracked=1):
    return execute("INSERT INTO club (name, league_id, tracked) VALUES (?, ?, ?)", (name, league_id, tracked))


def find_club(name):
    """Club id for a name (ignoring case and accents), or None."""
    wanted = _norm(name.strip())
    for row in query("SELECT id, name FROM club"):
        if _norm(row["name"]) == wanted:
            return row["id"]
    return None


def get_or_create_club(name, tracked=0):
    """Find a club by name or create it.

    Clubs created this way default to tracked=0, so they stay out of the
    player form's club dropdown but can still be used in fixtures.
    """
    return find_club(name) or add_club(name.strip(), None, tracked)


def club_calendar_source(club_id):
    row = _one("SELECT calendar_url FROM club WHERE id = ?", (club_id,))
    return row["calendar_url"] if row else None


def set_calendar_source(club_id, source):
    """Remember where a club's calendar came from. A club with a calendar is one you track."""
    execute("UPDATE club SET calendar_url = ?, tracked = 1 WHERE id = ?", (source, club_id))


# ---------- fixtures ----------

def fixtures_list():
    return query(
        """SELECT f.id, f.kickoff, f.competition, f.home_score, f.away_score, f.sofascore_url,
                  hc.name AS home, ac.name AS away,
                  (SELECT COUNT(*) FROM match_report r WHERE r.fixture_id = f.id) AS report_count
           FROM fixture f
           LEFT JOIN club hc ON hc.id = f.home_club_id
           LEFT JOIN club ac ON ac.id = f.away_club_id
           ORDER BY f.kickoff DESC, f.id DESC"""
    )


def fixture_options():
    """{fixture_id: '2026-11-12 AIK – Hammarby'} for dropdowns, newest first."""
    return {
        r["id"]: f"{(r['kickoff'] or '')[:10]} {r['home'] or '?'} – {r['away'] or '?'}".strip()
        for r in fixtures_list()
    }


def get_fixture(fixture_id):
    return _one("SELECT * FROM fixture WHERE id = ?", (fixture_id,))


def save_fixture(data, fixture_id=None):
    return _save("fixture", FIXTURE_FIELDS, data, fixture_id)


def fixture_report_count(fixture_id):
    return _one("SELECT COUNT(*) AS n FROM match_report WHERE fixture_id = ?", (fixture_id,))["n"]


def delete_fixture(fixture_id):
    """Raises sqlite3.IntegrityError if reports still point at it (ON DELETE RESTRICT)."""
    execute("DELETE FROM fixture WHERE id = ?", (fixture_id,))


# ---------- match reports ----------

def reports_for(player_id):
    return query(
        """SELECT r.*, f.kickoff, f.home_score, f.away_score,
                  hc.name AS home, ac.name AS away
           FROM match_report r
           LEFT JOIN fixture f ON f.id = r.fixture_id
           LEFT JOIN club hc ON hc.id = f.home_club_id
           LEFT JOIN club ac ON ac.id = f.away_club_id
           WHERE r.player_id = ?
           ORDER BY f.kickoff IS NULL, f.kickoff DESC, r.id DESC""",
        (player_id,),
    )


def get_report(report_id):
    return _one("SELECT * FROM match_report WHERE id = ?", (report_id,))


def save_report(data, report_id=None):
    return _save("match_report", REPORT_FIELDS, data, report_id)


def delete_report(report_id):
    execute("DELETE FROM match_report WHERE id = ?", (report_id,))


# ---------- calendar import and schedule ----------

def find_fixture_by_uid(uid):
    return _one("SELECT * FROM fixture WHERE ics_uid = ?", (uid,))


def find_unlinked_fixture(home_club_id, away_club_id, day):
    """A hand-entered fixture (no calendar id) for the same clubs within a day of `day` (YYYY-MM-DD)."""
    return _one(
        """SELECT * FROM fixture
           WHERE ics_uid IS NULL AND home_club_id = ? AND away_club_id = ?
             AND date(kickoff) BETWEEN date(?, '-1 day') AND date(?, '+1 day')
           ORDER BY kickoff LIMIT 1""",
        (home_club_id, away_club_id, day, day),
    )


def schedule(now, until=None, only_flagged=False):
    """Upcoming fixtures where a club has at least one of your players.

    now / until are local timestamps like '2026-11-12T18:00'. Each row gets a
    'players' text listing the players involved.
    """
    flagged = " AND (favorite = 1 OR watch_list = 1)" if only_flagged else ""
    by_club = {}
    for p in query(
        f"""SELECT name, current_club_id FROM player
            WHERE current_club_id IS NOT NULL{flagged} ORDER BY name COLLATE NOCASE"""
    ):
        by_club.setdefault(p["current_club_id"], []).append(p["name"])

    sql = """SELECT f.id, f.kickoff, f.competition, f.home_club_id, f.away_club_id,
                    hc.name AS home, ac.name AS away
             FROM fixture f
             LEFT JOIN club hc ON hc.id = f.home_club_id
             LEFT JOIN club ac ON ac.id = f.away_club_id
             WHERE f.kickoff >= ?"""
    args = [now]
    if until:
        sql += " AND f.kickoff < ?"
        args.append(until)
    rows = []
    for f in query(sql + " ORDER BY f.kickoff", args):
        names = by_club.get(f["home_club_id"], []) + by_club.get(f["away_club_id"], [])
        if names:
            f["players"] = ", ".join(names)
            rows.append(f)
    return rows


# ---------- schedule (fixtures involving players' current clubs) ----------

def fixtures_with_players(followed_only=True):
    """One row per (fixture, player) where the player's current club is home or away.

    followed_only=True keeps only favorites and watch-list players.
    """
    where = "AND (p.favorite = 1 OR p.watch_list = 1)" if followed_only else ""
    return query(
        f"""SELECT f.id AS fixture_id, f.kickoff, f.competition, f.home_score, f.away_score,
                   hc.name AS home, ac.name AS away,
                   p.id AS player_id, p.name AS player_name, p.favorite, p.watch_list,
                   EXISTS (SELECT 1 FROM match_report r
                           WHERE r.fixture_id = f.id AND r.player_id = p.id) AS has_report
            FROM fixture f
            JOIN player p ON p.current_club_id IN (f.home_club_id, f.away_club_id)
            LEFT JOIN club hc ON hc.id = f.home_club_id
            LEFT JOIN club ac ON ac.id = f.away_club_id
            WHERE f.kickoff IS NOT NULL {where}
            ORDER BY f.kickoff, f.id, p.name COLLATE NOCASE"""
    )


def fixture_detail(fixture_id):
    return _one(
        """SELECT f.id, f.kickoff, f.competition, f.home_score, f.away_score, f.sofascore_url,
                  hc.name AS home, ac.name AS away
           FROM fixture f
           LEFT JOIN club hc ON hc.id = f.home_club_id
           LEFT JOIN club ac ON ac.id = f.away_club_id
           WHERE f.id = ?""",
        (fixture_id,),
    )


def players_for_fixture(fixture_id):
    """All players whose current club plays in this fixture, favorites first."""
    return query(
        """SELECT p.id, p.name, p.favorite, p.watch_list,
                  EXISTS (SELECT 1 FROM match_report r
                          WHERE r.fixture_id = f.id AND r.player_id = p.id) AS has_report
           FROM fixture f
           JOIN player p ON p.current_club_id IN (f.home_club_id, f.away_club_id)
           WHERE f.id = ?
           ORDER BY p.favorite DESC, p.watch_list DESC, p.name COLLATE NOCASE""",
        (fixture_id,),
    )
