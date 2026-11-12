"""Creates the scouting database. Run once: python create_db.py

Other scripts import connect() from here so foreign keys are always enforced.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "scouting.db"

SCHEMA = """
CREATE TABLE nation (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  abbreviation TEXT
);

CREATE TABLE league (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  nation_id INTEGER REFERENCES nation(id),
  tier INTEGER
);

CREATE TABLE club (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  league_id INTEGER REFERENCES league(id),
  tracked INTEGER NOT NULL DEFAULT 1,   -- 0 = auto-created (e.g. calendar opponents)
  calendar_url TEXT                     -- Fotmob .ics link, optional
);

CREATE TABLE player (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  dob DATE CHECK (dob is NULL OR date(dob) IS dob),                             -- 'YYYY-MM-DD'
  position TEXT,
  nationality_id INTEGER REFERENCES nation(id),
  current_club_id INTEGER REFERENCES club(id),
  transfermarkt_url TEXT,
  contract_expiry DATE CHECK (contract_expiry IS NULL OR date(contract_expiry) IS contract_expiry),
  market_value_eur INTEGER,
  homegrown_sweden INTEGER NOT NULL DEFAULT 0,
  linked_with_aik INTEGER NOT NULL DEFAULT 0,
  favorite INTEGER NOT NULL DEFAULT 0,
  watch_list INTEGER NOT NULL DEFAULT 0,
  comments TEXT,
  photo_path TEXT,
  spider_path TEXT
);

CREATE TABLE season_stats (
  id INTEGER PRIMARY KEY,
  player_id INTEGER NOT NULL REFERENCES player(id) ON DELETE CASCADE,
  season TEXT NOT NULL,                 -- e.g. '2026'
  club_id INTEGER REFERENCES club(id),
  matches_played INTEGER,
  matches_started INTEGER,
  minutes INTEGER,
  goals INTEGER,
  assists INTEGER,
  updated DATE CHECK (updated IS NULL OR date(updated) IS updated) DEFAULT (date('now'))
);

CREATE TABLE transfer (
  id INTEGER PRIMARY KEY,
  player_id INTEGER NOT NULL REFERENCES player(id) ON DELETE CASCADE,
  from_club_id INTEGER REFERENCES club(id),
  from_club_text TEXT,
  to_club_id INTEGER REFERENCES club(id),
  to_club_text TEXT,
  date DATE CHECK (date IS NULL OR date(date) IS date),
  fee_eur INTEGER,
  is_loan INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE fixture (
  id INTEGER PRIMARY KEY,
  ics_uid TEXT UNIQUE,                  -- prevents duplicates on calendar re-import
  home_club_id INTEGER REFERENCES club(id),
  away_club_id INTEGER REFERENCES club(id),
  kickoff DATETIME CHECK (kickoff IS NULL OR strftime('%Y-%m-%dT%H:%M', kickoff) IS kickoff),                         -- 'YYYY-MM-DDTHH:MM'
  competition TEXT,
  home_score INTEGER,
  away_score INTEGER,
  sofascore_url TEXT
);

CREATE TABLE match_report (
  id INTEGER PRIMARY KEY,
  player_id INTEGER NOT NULL REFERENCES player(id) ON DELETE CASCADE,
  fixture_id INTEGER REFERENCES fixture(id) ON DELETE RESTRICT,  -- optional
  position TEXT,
  minutes INTEGER,
  goals INTEGER,
  assists INTEGER,
  sofascore_rating REAL CHECK (sofascore_rating BETWEEN 1 AND 10),
  my_rating REAL CHECK (my_rating BETWEEN 1 AND 10),
  comments TEXT,
  key_moments TEXT
);

CREATE INDEX idx_player_club ON player(current_club_id);
CREATE INDEX idx_stats_player ON season_stats(player_id);
CREATE INDEX idx_fixture_kickoff ON fixture(kickoff);
CREATE INDEX idx_report_player ON match_report(player_id);
CREATE INDEX idx_report_fixture ON match_report(fixture_id);
"""


def connect(path=DB_PATH):
    """Open a connection with foreign keys on (SQLite needs this per connection)."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def create_db(path=DB_PATH):
    if Path(path).exists():
        raise SystemExit(f"{path} already exists. Delete it first if you want a fresh start.")
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Created {path}")


if __name__ == "__main__":
    create_db()