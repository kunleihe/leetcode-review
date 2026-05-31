import sqlite3
from datetime import date, datetime, timezone
import config

DB_PATH = config.DB_PATH


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS problems (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                number INTEGER NOT NULL,
                difficulty TEXT NOT NULL,
                url TEXT NOT NULL,
                first_solved_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviews (
                problem_id TEXT PRIMARY KEY REFERENCES problems(id),
                due_date TEXT NOT NULL,
                interval INTEGER NOT NULL DEFAULT 1,
                ease_factor REAL NOT NULL DEFAULT 2.5,
                repetitions INTEGER NOT NULL DEFAULT 0,
                last_reviewed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                synced_at INTEGER NOT NULL,
                new_problems INTEGER NOT NULL DEFAULT 0
            );
        """)


def upsert_problem(slug, title, number, difficulty, url, first_solved_at):
    with _conn() as conn:
        conn.execute("""
            INSERT INTO problems (id, title, number, difficulty, url, first_solved_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
        """, (slug, title, number, difficulty, url, first_solved_at))


def get_problem(slug):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM problems WHERE id = ?", (slug,)).fetchone()
        return dict(row) if row else None


def init_review(problem_id, due_date):
    with _conn() as conn:
        conn.execute("""
            INSERT INTO reviews (problem_id, due_date, interval, ease_factor, repetitions, last_reviewed_at)
            VALUES (?, ?, 1, 2.5, 0, NULL)
            ON CONFLICT(problem_id) DO NOTHING
        """, (problem_id, due_date))


def get_review(problem_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE problem_id = ?", (problem_id,)).fetchone()
        return dict(row) if row else None


def update_review(problem_id, due_date, interval, ease_factor, repetitions, last_reviewed_at):
    with _conn() as conn:
        cur = conn.execute("""
            UPDATE reviews
            SET due_date=?, interval=?, ease_factor=?, repetitions=?, last_reviewed_at=?
            WHERE problem_id=?
        """, (due_date, interval, ease_factor, repetitions, last_reviewed_at, problem_id))
        if cur.rowcount == 0:
            raise ValueError(f"No review row for problem_id={problem_id!r}")


def get_due_reviews(today_str):
    with _conn() as conn:
        rows = conn.execute("""
            SELECT r.*, p.title, p.number, p.difficulty, p.url
            FROM reviews r JOIN problems p ON r.problem_id = p.id
            WHERE r.due_date <= ?
            ORDER BY r.due_date ASC
        """, (today_str,)).fetchall()
        return [dict(r) for r in rows]


def get_future_reviews(today_str):
    with _conn() as conn:
        rows = conn.execute("""
            SELECT r.*, p.title, p.number, p.difficulty, p.url
            FROM reviews r JOIN problems p ON r.problem_id = p.id
            WHERE r.due_date > ?
            ORDER BY r.due_date ASC
        """, (today_str,)).fetchall()
        return [dict(r) for r in rows]


def log_sync(synced_at, new_problems):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sync_log (synced_at, new_problems) VALUES (?, ?)",
            (synced_at, new_problems)
        )


def get_last_sync():
    with _conn() as conn:
        row = conn.execute("SELECT MAX(synced_at) as ts FROM sync_log").fetchone()
        return row["ts"] if row and row["ts"] is not None else None


def synced_today():
    last = get_last_sync()
    if last is None:
        return False
    return datetime.fromtimestamp(last, tz=timezone.utc).date() == date.today()
