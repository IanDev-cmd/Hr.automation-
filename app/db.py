"""SQLite desk store. PostgreSQL uses the same columns in schema.sql."""

import sqlite3
from pathlib import Path

from app.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
_conn: sqlite3.Connection | None = None

DDL = """
CREATE TABLE IF NOT EXISTS homes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  region TEXT NOT NULL,
  sleep_in_rate REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
  id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  home_id TEXT,
  stage TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  rejected_at TEXT,
  on_reapply_watchlist INTEGER NOT NULL DEFAULT 0,
  completion_percent INTEGER NOT NULL DEFAULT 0,
  rejection_reason TEXT,
  reapply_eligible_at TEXT,
  skills_tags TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS screening_answers (
  candidate_id TEXT PRIMARY KEY,
  nvq_level_3 INTEGER NOT NULL,
  driving_licence_one_year INTEGER NOT NULL,
  right_to_work INTEGER NOT NULL,
  years_experience REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS signature_audits (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  signer_email TEXT NOT NULL,
  ip_address TEXT NOT NULL,
  user_agent TEXT NOT NULL,
  signed_at TEXT NOT NULL,
  document_sha256 TEXT NOT NULL,
  token_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reference_requests (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  referee_name TEXT NOT NULL,
  referee_email TEXT NOT NULL DEFAULT '',
  sent_at TEXT NOT NULL,
  dates_only INTEGER NOT NULL DEFAULT 0,
  received INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reference_chases (
  id TEXT PRIMARY KEY,
  reference_id TEXT NOT NULL,
  chased_at TEXT NOT NULL,
  template_name TEXT NOT NULL,
  note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS home_visits (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  home_id TEXT NOT NULL,
  visit_at TEXT NOT NULL,
  visitor_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS training_bookings (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  course TEXT NOT NULL,
  booked_for TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dbs_checks (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  certificate_number TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  next_due TEXT
);
CREATE TABLE IF NOT EXISTS reengagement_alerts (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  note TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interviews (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  join_url TEXT NOT NULL DEFAULT '',
  recording_name TEXT NOT NULL DEFAULT '',
  transcript_text TEXT NOT NULL DEFAULT ''
);
"""


def _path_from_url(url: str) -> str:
    if not url or url in {"sqlite", "sqlite://"} or ":memory:" in url:
        if url and ":memory:" in url:
            return ":memory:"
        folder = ROOT / "data"
        folder.mkdir(exist_ok=True)
        return str(folder / "hr.sqlite")
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    if url.startswith("postgres"):
        raise RuntimeError("PostgreSQL is declared in schema.sql. Set DATABASE_URL to sqlite for this process.")
    return url


def reset_db(url: str | None = None) -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        _conn.close()
    chosen = get_settings().database_url if url is None else url
    _conn = sqlite3.connect(_path_from_url(chosen), check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(DDL)
    _conn.executemany(
        "INSERT OR IGNORE INTO homes (id, name, region, sleep_in_rate) VALUES (?, ?, ?, ?)",
        [
            ("mayfield", "Mayfield Lodge", "Bournemouth", 63.0),
            ("rainbow", "Rainbow Lodge", "Bournemouth", 63.0),
            ("fernleigh", "Fernleigh House", "Cornwall", 60.0),
        ],
    )
    _conn.commit()
    return _conn


def init_db() -> sqlite3.Connection:
    if _conn is None:
        return reset_db()
    return _conn


def connection() -> sqlite3.Connection:
    return init_db()


def home_id(name: str) -> str | None:
    row = connection().execute("SELECT id FROM homes WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else None


def home_name(home: str) -> str | None:
    row = connection().execute("SELECT name FROM homes WHERE id = ? OR name = ?", (home, home)).fetchone()
    return row["name"] if row else None
