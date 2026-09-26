import sqlite3
import time
import random
import string
from contextlib import contextmanager

from officer_directory import TALUK_CODE

DB_PATH = "grieveye.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS citizens (
                chat_id INTEGER PRIMARY KEY,
                name TEXT,
                language TEXT DEFAULT 'kn',
                consent_at REAL,
                withdrawn_at REAL
            );

            CREATE TABLE IF NOT EXISTS officers (
                post TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                registered_at REAL
            );

            CREATE TABLE IF NOT EXISTS cases (
                tracking_id TEXT PRIMARY KEY,
                citizen_chat_id INTEGER NOT NULL,
                citizen_name TEXT,
                village TEXT,
                category TEXT,
                description TEXT,
                raw_text TEXT,
                media_type TEXT,          -- voice, photo or NULL
                media_file_id TEXT,       -- Telegram file_id, re-sent to the officer
                ai_confidence REAL,
                restricted INTEGER DEFAULT 0,
                original_post TEXT,
                officer_post TEXT,
                status TEXT,
                reopen_count INTEGER DEFAULT 0,
                citizen_rating INTEGER,
                is_seed INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            );

            -- Every status change. The scorecard is computed from this table.
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_id TEXT NOT NULL,
                at REAL NOT NULL,
                actor TEXT NOT NULL,      -- citizen, officer, system, triage
                officer_post TEXT,        -- post holding the case after this event
                from_post TEXT,           -- post that held it before (differs on escalation)
                from_status TEXT,
                to_status TEXT NOT NULL,
                note TEXT,
                proof_file_id TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        # Columns added after the first release; added in place so existing data is kept.
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(cases)")}
        for column, kind in [
            ("lat", "REAL"), ("lon", "REAL"),
            ("location_source", "TEXT"),       # pin (shared by the citizen) or photo (from EXIF)
            ("proof_lat", "REAL"), ("proof_lon", "REAL"),
            ("proof_distance_m", "REAL"),      # officer's proof location to the complaint location
        ]:
            if column not in existing:
                conn.execute(f"ALTER TABLE cases ADD COLUMN {column} {kind}")


# ---------- demo clock ----------
# now() = real time + an offset, so /tick48 can make 48 hours pass on stage.

def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def pop_setting(key):
    value = get_setting(key)
    with get_conn() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    return value


def now() -> float:
    return time.time() + float(get_setting("clock_offset", 0))


def advance_clock(hours: float):
    set_setting("clock_offset", float(get_setting("clock_offset", 0)) + hours * 3600)


# ---------- citizens ----------

def get_citizen(chat_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM citizens WHERE chat_id = ?", (chat_id,)).fetchone()
        return dict(row) if row else None


def upsert_citizen(chat_id, **fields):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO citizens (chat_id) VALUES (?)", (chat_id,))
        for key, value in fields.items():
            conn.execute(f"UPDATE citizens SET {key} = ? WHERE chat_id = ?", (value, chat_id))


def withdraw_citizen(chat_id):
    """DPDP consent withdrawal: drop personal details, keep anonymised case stats."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE citizens SET name = NULL, consent_at = NULL, withdrawn_at = ? WHERE chat_id = ?",
            (time.time(), chat_id),
        )
        conn.execute(
            """UPDATE cases SET citizen_name = NULL, raw_text = NULL, media_file_id = NULL,
               media_type = NULL WHERE citizen_chat_id = ?""",
            (chat_id,),
        )


# ---------- officers ----------

def register_officer(post, chat_id):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO officers (post, chat_id, registered_at) VALUES (?, ?, ?) "
            "ON CONFLICT(post) DO UPDATE SET chat_id = excluded.chat_id, "
            "registered_at = excluded.registered_at",
            (post, chat_id, time.time()),
        )


def get_officer_chat(post):
    with get_conn() as conn:
        row = conn.execute("SELECT chat_id FROM officers WHERE post = ?", (post,)).fetchone()
        return row["chat_id"] if row else None


def get_posts_for_chat(chat_id):
    with get_conn() as conn:
        rows = conn.execute("SELECT post FROM officers WHERE chat_id = ?", (chat_id,)).fetchall()
        return [r["post"] for r in rows]


# ---------- cases ----------

def new_tracking_id() -> str:
    alphabet = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"
    with get_conn() as conn:
        while True:
            tid = f"GRV-{TALUK_CODE}-" + "".join(random.choices(alphabet, k=5))
            if not conn.execute("SELECT 1 FROM cases WHERE tracking_id = ?", (tid,)).fetchone():
                return tid


def insert_case(**fields) -> str:
    tracking_id = fields.pop("tracking_id", None) or new_tracking_id()
    fields["tracking_id"] = tracking_id
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    with get_conn() as conn:
        conn.execute(f"INSERT INTO cases ({cols}) VALUES ({marks})", tuple(fields.values()))
    return tracking_id


def update_case(tracking_id, **fields):
    sets = ", ".join(f"{k} = ?" for k in fields)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE cases SET {sets} WHERE tracking_id = ?",
            (*fields.values(), tracking_id),
        )


def add_event(tracking_id, at, actor, officer_post, from_status, to_status, note=None,
              proof_file_id=None, from_post=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO events (tracking_id, at, actor, officer_post, from_post, from_status,
               to_status, note, proof_file_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tracking_id, at, actor, officer_post, from_post or officer_post, from_status,
             to_status, note, proof_file_id),
        )


def get_case(tracking_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM cases WHERE tracking_id = ?", (tracking_id.upper(),)
        ).fetchone()
        return dict(row) if row else None


def get_events(tracking_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE tracking_id = ? ORDER BY at, id", (tracking_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def last_proof(tracking_id: str):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT proof_file_id FROM events WHERE tracking_id = ? AND proof_file_id IS NOT NULL
               ORDER BY at DESC, id DESC LIMIT 1""",
            (tracking_id,),
        ).fetchone()
        return row["proof_file_id"] if row else None


def cases_with_status(*statuses):
    marks = ", ".join("?" for _ in statuses)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM cases WHERE status IN ({marks}) ORDER BY created_at", statuses
        ).fetchall()
        return [dict(r) for r in rows]


def cases_for_posts(posts, open_only=True):
    if not posts:
        return []
    marks = ", ".join("?" for _ in posts)
    sql = f"SELECT * FROM cases WHERE officer_post IN ({marks})"
    if open_only:
        sql += " AND status NOT IN ('VERIFIED', 'RESOLVED_UNVERIFIED')"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY created_at", posts).fetchall()]


def all_cases():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM cases").fetchall()]


def all_events():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY at, id").fetchall()]


def recent_events(limit=12):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.*, c.village, c.category FROM events e
               JOIN cases c ON c.tracking_id = e.tracking_id
               WHERE c.is_seed = 0 ORDER BY e.at DESC, e.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def reset_all():
    with get_conn() as conn:
        conn.executescript(
            "DELETE FROM cases; DELETE FROM events; DELETE FROM settings;"
        )
