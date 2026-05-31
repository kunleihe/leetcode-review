import json
import time
from unittest.mock import patch
import pytest
import db


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    import app as flask_app
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<html" in resp.data.lower()


def test_api_reviews_empty(client):
    data = json.loads(client.get("/api/reviews").data)
    assert data["due"] == []
    assert data["future"] == []


def test_api_reviews_returns_due(client):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    db.init_review("two-sum", "2020-01-01")
    data = json.loads(client.get("/api/reviews").data)
    assert any(r["problem_id"] == "two-sum" for r in data["due"])


def test_api_review_post_good(client):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    db.init_review("two-sum", "2020-01-01")
    resp = client.post("/api/review/two-sum",
                       json={"rating": "Good"},
                       content_type="application/json")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "due_date" in data
    assert db.get_review("two-sum")["repetitions"] == 1


def test_api_review_post_invalid_rating(client):
    db.upsert_problem("two-sum", "Two Sum", 1, "Easy",
                      "https://leetcode.com/problems/two-sum/", 1700000000)
    db.init_review("two-sum", "2020-01-01")
    resp = client.post("/api/review/two-sum",
                       json={"rating": "Perfect"},
                       content_type="application/json")
    assert resp.status_code == 400


def test_api_sync_starts_background_sync(client):
    import app as flask_app
    with patch.object(flask_app, "_run_sync_bg") as m, \
         patch("threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        resp = client.post("/api/sync")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] in ("started", "already_running")
        # Release the lock in case it was acquired
        if flask_app._sync_lock.locked():
            flask_app._sync_lock.release()


def test_api_sync_status(client):
    import app as flask_app
    resp = client.get("/api/sync/status")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "running" in data
    assert "new_problems" in data
    assert "error" in data
