import sqlite3
import time
import pytest
import db


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    return db_path


def test_init_creates_tables(tmp_db):
    conn = sqlite3.connect(tmp_db)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert {"problems", "reviews", "sync_log"} <= tables


def test_upsert_problem(tmp_db):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    p = db.get_problem("two-sum")
    assert p["title"] == "Two Sum"
    assert p["number"] == 1


def test_upsert_problem_idempotent(tmp_db):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    conn = sqlite3.connect(tmp_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM problems WHERE id='two-sum'"
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_init_review(tmp_db):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    db.init_review("two-sum", "2026-05-31")
    r = db.get_review("two-sum")
    assert r["due_date"] == "2026-05-31"
    assert r["interval"] == 1
    assert abs(r["ease_factor"] - 2.5) < 0.001
    assert r["repetitions"] == 0
    assert r["last_reviewed_at"] is None


def test_init_review_skips_existing(tmp_db):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    db.init_review("two-sum", "2026-05-31")
    db.init_review("two-sum", "2026-06-01")  # must not overwrite
    assert db.get_review("two-sum")["due_date"] == "2026-05-31"


def test_update_review(tmp_db):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    db.init_review("two-sum", "2026-05-31")
    db.update_review("two-sum",
                     due_date="2026-06-10", interval=10,
                     ease_factor=2.6, repetitions=1,
                     last_reviewed_at="2026-05-31")
    r = db.get_review("two-sum")
    assert r["due_date"] == "2026-06-10"
    assert r["interval"] == 10
    assert r["repetitions"] == 1


def test_get_due_reviews(tmp_db):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    db.upsert_problem("add-two-numbers", "Add Two Numbers", 2, "Medium",
                      "https://leetcode.com/problems/add-two-numbers/", 1700000001)
    db.init_review("two-sum", "2026-05-28")        # overdue
    db.init_review("add-two-numbers", "2026-06-10") # future
    due = db.get_due_reviews("2026-05-30")
    slugs = [r["problem_id"] for r in due]
    assert "two-sum" in slugs
    assert "add-two-numbers" not in slugs


def test_get_future_reviews(tmp_db):
    db.upsert_problem("add-two-numbers", "Add Two Numbers", 2, "Medium",
                      "https://leetcode.com/problems/add-two-numbers/", 1700000001)
    db.init_review("add-two-numbers", "2026-06-10")
    future = db.get_future_reviews("2026-05-30")
    assert any(r["problem_id"] == "add-two-numbers" for r in future)


def test_log_sync_and_get_last(tmp_db):
    db.log_sync(1714000000, 5)
    assert db.get_last_sync() == 1714000000


def test_get_last_sync_none(tmp_db):
    assert db.get_last_sync() is None


def test_synced_today(tmp_db):
    db.log_sync(int(time.time()), 0)
    assert db.synced_today() is True


def test_not_synced_today(tmp_db):
    assert db.synced_today() is False
