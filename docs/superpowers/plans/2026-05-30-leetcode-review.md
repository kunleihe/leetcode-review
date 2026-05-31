# LeetCode 记忆曲线复习工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Flask web app that fetches LeetCode submission history via GraphQL, schedules SM-2 spaced repetition reviews, and presents due problems in a table where users rate mastery to trigger the next review date.

**Architecture:** Flask serves a single-page HTML app backed by SQLite. LeetCode's unofficial GraphQL API is queried on first page load (full history) and on each subsequent day's first load (incremental). SM-2 is computed in pure Python. The app auto-starts on login via a macOS LaunchAgent.

**Tech Stack:** Python 3.10+, Flask 3.x, sqlite3 (stdlib), requests, pytest, pytest-mock

---

## File Map

| File | Responsibility |
|------|---------------|
| `config.py` | LEETCODE_SESSION and app settings |
| `db.py` | SQLite schema init and all CRUD |
| `sm2.py` | Pure SM-2 algorithm, no I/O |
| `lc_client.py` | LeetCode GraphQL HTTP client |
| `app.py` | Flask app, all routes |
| `templates/index.html` | Single-page table UI |
| `install.py` | macOS LaunchAgent setup/teardown |
| `pyproject.toml` | Python dependencies (uv) |
| `tests/test_sm2.py` | SM-2 unit tests |
| `tests/test_db.py` | Database layer tests |
| `tests/test_lc_client.py` | LeetCode client tests (mocked HTTP) |
| `tests/test_app.py` | Flask route integration tests |

---

### Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `config.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Install uv (if not already installed)**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Expected: `uv` available in PATH. Verify with `uv --version`.

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "leetcode-review"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "flask==3.0.3",
    "requests==2.32.3",
]

[tool.uv]
dev-dependencies = [
    "pytest==8.2.0",
    "pytest-mock==3.14.0",
]
```

- [ ] **Step 3: Install dependencies**

```bash
uv sync
```

Expected: uv creates `.venv/` and installs all packages. Output ends with `Done.`

- [ ] **Step 4: Create config.py**

```python
import os

LEETCODE_SESSION = os.environ.get("LEETCODE_SESSION", "")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leetcode.db")
PORT = 5000
```

- [ ] **Step 5: Create tests directory**

```bash
mkdir -p tests && touch tests/__init__.py
```

- [ ] **Step 6: Initialize git and commit**

```bash
git init
echo ".venv/" >> .gitignore
echo "leetcode.db" >> .gitignore
git add pyproject.toml uv.lock .gitignore config.py tests/__init__.py
git commit -m "feat: project scaffold"
```

---

### Task 2: Database Layer

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Implement db.py**

```python
import sqlite3
from datetime import date, datetime, timezone
import config

DB_PATH = config.DB_PATH


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
        conn.execute("""
            UPDATE reviews
            SET due_date=?, interval=?, ease_factor=?, repetitions=?, last_reviewed_at=?
            WHERE problem_id=?
        """, (due_date, interval, ease_factor, repetitions, last_reviewed_at, problem_id))


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_db.py -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: database layer with schema and CRUD"
```

---

### Task 3: SM-2 Algorithm

**Files:**
- Create: `sm2.py`
- Create: `tests/test_sm2.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sm2.py`:

```python
import pytest
import sm2


def test_quality_mapping():
    assert sm2.QUALITY["Again"] == 1
    assert sm2.QUALITY["Hard"] == 2
    assert sm2.QUALITY["Good"] == 4
    assert sm2.QUALITY["Easy"] == 5


def test_again_resets():
    r = sm2.calculate("Again", interval=10, ease_factor=2.5, repetitions=3, today="2026-05-30")
    assert r["interval"] == 1
    assert r["repetitions"] == 0


def test_hard_resets():
    r = sm2.calculate("Hard", interval=10, ease_factor=2.5, repetitions=3, today="2026-05-30")
    assert r["interval"] == 1
    assert r["repetitions"] == 0


def test_good_advances_interval():
    r = sm2.calculate("Good", interval=6, ease_factor=2.5, repetitions=2, today="2026-05-30")
    assert r["interval"] == max(1, round(6 * 2.5))
    assert r["repetitions"] == 3


def test_easy_advances_interval():
    r = sm2.calculate("Easy", interval=6, ease_factor=2.5, repetitions=2, today="2026-05-30")
    assert r["interval"] == max(1, round(6 * 2.5))
    assert r["repetitions"] == 3


def test_interval_minimum_one():
    r = sm2.calculate("Good", interval=0, ease_factor=1.3, repetitions=0, today="2026-05-30")
    assert r["interval"] >= 1


def test_ease_decreases_on_hard():
    r = sm2.calculate("Hard", interval=1, ease_factor=2.5, repetitions=0, today="2026-05-30")
    assert r["ease_factor"] < 2.5


def test_ease_increases_on_easy():
    r = sm2.calculate("Easy", interval=1, ease_factor=2.5, repetitions=0, today="2026-05-30")
    assert r["ease_factor"] > 2.5


def test_ease_minimum_1_3():
    r = sm2.calculate("Again", interval=1, ease_factor=1.3, repetitions=0, today="2026-05-30")
    assert r["ease_factor"] >= 1.3


def test_due_date_is_iso_string():
    r = sm2.calculate("Good", interval=3, ease_factor=2.5, repetitions=1, today="2026-05-30")
    parts = r["due_date"].split("-")
    assert len(parts) == 3
    assert parts[0] == "2026"


def test_due_date_offset_from_today():
    r = sm2.calculate("Good", interval=3, ease_factor=2.5, repetitions=1, today="2026-05-30")
    # interval=3, ease=2.5 → new_interval = max(1, round(3*2.5)) = 8
    assert r["due_date"] == "2026-06-07"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_sm2.py -v
```

Expected: `ModuleNotFoundError: No module named 'sm2'`

- [ ] **Step 3: Implement sm2.py**

```python
from datetime import date, timedelta

QUALITY = {"Again": 1, "Hard": 2, "Good": 4, "Easy": 5}


def calculate(rating, interval, ease_factor, repetitions, today):
    quality = QUALITY[rating]

    if quality >= 3:
        new_interval = max(1, round(interval * ease_factor))
        new_repetitions = repetitions + 1
    else:
        new_interval = 1
        new_repetitions = 0

    new_ease = ease_factor + 0.1 - (5 - quality) * 0.08 + (5 - quality) ** 2 * 0.02
    new_ease = round(max(1.3, new_ease), 4)

    due = date.fromisoformat(today) + timedelta(days=new_interval)

    return {
        "interval": new_interval,
        "ease_factor": new_ease,
        "repetitions": new_repetitions,
        "due_date": due.isoformat(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_sm2.py -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sm2.py tests/test_sm2.py
git commit -m "feat: SM-2 spaced repetition algorithm"
```

---

### Task 4: LeetCode Client

**Files:**
- Create: `lc_client.py`
- Create: `tests/test_lc_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_lc_client.py`:

```python
from unittest.mock import MagicMock, patch
import pytest
import lc_client

MOCK_SUB_PAGE = {
    "data": {
        "submissionList": {
            "hasNext": False,
            "submissions": [
                {"titleSlug": "two-sum", "title": "Two Sum",
                 "statusDisplay": "Accepted", "timestamp": "1700000000", "lang": "python3"},
                {"titleSlug": "two-sum", "title": "Two Sum",
                 "statusDisplay": "Wrong Answer", "timestamp": "1699990000", "lang": "python3"},
                {"titleSlug": "add-two-numbers", "title": "Add Two Numbers",
                 "statusDisplay": "Accepted", "timestamp": "1700100000", "lang": "python3"},
            ]
        }
    }
}

MOCK_QUESTION = {
    "data": {
        "question": {"questionFrontendId": "1", "difficulty": "Easy"}
    }
}


def mock_resp(data, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = data
    return m


def test_fetch_ac_filters_wrong_answer():
    with patch("lc_client.requests.post", return_value=mock_resp(MOCK_SUB_PAGE)):
        result = lc_client.fetch_ac_submissions(session="fake", since_ts=0, delay=0)
    slugs = [r["titleSlug"] for r in result]
    # Wrong Answer for two-sum must be excluded; only one entry per slug
    assert slugs.count("two-sum") == 1
    assert "add-two-numbers" in slugs


def test_fetch_ac_deduplicates_keeps_earliest_ac():
    with patch("lc_client.requests.post", return_value=mock_resp(MOCK_SUB_PAGE)):
        result = lc_client.fetch_ac_submissions(session="fake", since_ts=0, delay=0)
    two_sum = next(r for r in result if r["titleSlug"] == "two-sum")
    assert two_sum["timestamp"] == "1700000000"


def test_fetch_ac_filters_by_since_ts():
    with patch("lc_client.requests.post", return_value=mock_resp(MOCK_SUB_PAGE)):
        result = lc_client.fetch_ac_submissions(session="fake", since_ts=1700050000, delay=0)
    slugs = [r["titleSlug"] for r in result]
    assert "two-sum" not in slugs
    assert "add-two-numbers" in slugs


def test_fetch_ac_raises_auth_error_on_403():
    with patch("lc_client.requests.post", return_value=mock_resp({}, status=403)):
        with pytest.raises(lc_client.AuthError):
            lc_client.fetch_ac_submissions(session="bad", since_ts=0, delay=0)


def test_fetch_question_info():
    with patch("lc_client.requests.post", return_value=mock_resp(MOCK_QUESTION)):
        info = lc_client.fetch_question_info("two-sum", session="fake", delay=0)
    assert info["difficulty"] == "Easy"
    assert info["number"] == "1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_lc_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'lc_client'`

- [ ] **Step 3: Implement lc_client.py**

```python
import time
import requests

GRAPHQL_URL = "https://leetcode.com/graphql"


class AuthError(Exception):
    pass


def _headers(session):
    return {
        "Cookie": f"LEETCODE_SESSION={session}",
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
    }


def _post(payload, session):
    resp = requests.post(GRAPHQL_URL, json=payload, headers=_headers(session))
    if resp.status_code in (401, 403):
        raise AuthError("LeetCode session cookie is invalid or expired.")
    return resp


_SUBMISSION_LIST_QUERY = """
query submissionList($offset: Int!, $limit: Int!) {
  submissionList(offset: $offset, limit: $limit, questionSlug: "") {
    hasNext
    submissions {
      titleSlug
      title
      statusDisplay
      timestamp
      lang
    }
  }
}
"""

_QUESTION_INFO_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId
    difficulty
  }
}
"""


def fetch_ac_submissions(session, since_ts=0, delay=0.5):
    offset = 0
    limit = 20
    seen = {}  # slug -> earliest AC submission dict

    while True:
        payload = {
            "query": _SUBMISSION_LIST_QUERY,
            "variables": {"offset": offset, "limit": limit},
        }
        data = _post(payload, session).json()["data"]["submissionList"]

        stop = False
        for sub in data["submissions"]:
            if sub["statusDisplay"] != "Accepted":
                continue
            ts = int(sub["timestamp"])
            if ts < since_ts:
                stop = True
                break
            slug = sub["titleSlug"]
            if slug not in seen or ts < int(seen[slug]["timestamp"]):
                seen[slug] = sub

        if stop or not data["hasNext"]:
            break

        offset += limit
        time.sleep(delay)

    return list(seen.values())


def fetch_question_info(slug, session, delay=0.3):
    payload = {"query": _QUESTION_INFO_QUERY, "variables": {"titleSlug": slug}}
    q = _post(payload, session).json()["data"]["question"]
    time.sleep(delay)
    return {"number": q["questionFrontendId"], "difficulty": q["difficulty"]}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_lc_client.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lc_client.py tests/test_lc_client.py
git commit -m "feat: LeetCode GraphQL client with pagination and auth"
```

---

### Task 5: Flask App and API Routes

**Files:**
- Create: `app.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_app.py`:

```python
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


def test_api_sync_calls_run_sync(client):
    import app as flask_app
    with patch.object(flask_app, "run_sync", return_value={"new_problems": 2, "error": None}) as m:
        resp = client.post("/api/sync")
        assert resp.status_code == 200
        m.assert_called_once()
        assert json.loads(resp.data)["new_problems"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_app.py -v
```

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Implement app.py**

```python
import logging
import time
from datetime import date
from flask import Flask, jsonify, render_template, request

import config
import db
import lc_client
import sm2

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)


def run_sync():
    session = config.LEETCODE_SESSION
    if not session:
        return {"new_problems": 0, "error": "LEETCODE_SESSION not configured in config.py"}
    try:
        last_ts = db.get_last_sync() or 0
        submissions = lc_client.fetch_ac_submissions(session=session, since_ts=last_ts)
        count = 0
        for sub in submissions:
            slug = sub["titleSlug"]
            if db.get_problem(slug):
                continue
            try:
                info = lc_client.fetch_question_info(slug, session=session)
            except Exception:
                info = {"number": 0, "difficulty": "Unknown"}
            ts = int(sub["timestamp"])
            db.upsert_problem(
                slug, sub["title"], int(info["number"]),
                info["difficulty"],
                f"https://leetcode.com/problems/{slug}/",
                ts,
            )
            db.init_review(slug, date.fromtimestamp(ts).isoformat())
            count += 1
        db.log_sync(int(time.time()), count)
        return {"new_problems": count, "error": None}
    except lc_client.AuthError as e:
        return {"new_problems": 0, "error": str(e)}
    except Exception as e:
        log.exception("Sync failed")
        return {"new_problems": 0, "error": str(e)}


@app.before_request
def auto_sync_on_index():
    if request.path == "/" and not db.synced_today():
        run_sync()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/reviews")
def api_reviews():
    today = date.today().isoformat()
    return jsonify({
        "due": db.get_due_reviews(today),
        "future": db.get_future_reviews(today),
        "today": today,
    })


@app.route("/api/review/<problem_id>", methods=["POST"])
def api_review(problem_id):
    rating = request.json.get("rating")
    if rating not in sm2.QUALITY:
        return jsonify({"error": f"Invalid rating '{rating}'"}), 400
    review = db.get_review(problem_id)
    if not review:
        return jsonify({"error": "Problem not found"}), 404
    today = date.today().isoformat()
    result = sm2.calculate(
        rating=rating,
        interval=review["interval"],
        ease_factor=review["ease_factor"],
        repetitions=review["repetitions"],
        today=today,
    )
    db.update_review(
        problem_id,
        due_date=result["due_date"],
        interval=result["interval"],
        ease_factor=result["ease_factor"],
        repetitions=result["repetitions"],
        last_reviewed_at=today,
    )
    return jsonify(result)


@app.route("/api/sync", methods=["POST"])
def api_sync():
    return jsonify(run_sync())


if __name__ == "__main__":
    db.init_db()
    app.run(port=config.PORT, debug=False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_app.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: Flask app with review, sync, and auto-sync routes"
```

---

### Task 6: Frontend UI

**Files:**
- Create: `templates/index.html`

- [ ] **Step 1: Create templates directory**

```bash
mkdir -p templates
```

- [ ] **Step 2: Create templates/index.html**

```html
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LeetCode Review</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; color: #333; }
    #banner { display: none; background: #ff4d4f; color: white; padding: 10px 20px; text-align: center; font-size: 14px; }
    header { background: white; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; }
    header h1 { font-size: 18px; font-weight: 600; }
    #stats { font-size: 14px; color: #666; margin-top: 4px; }
    .header-right { text-align: right; }
    #sync-btn { padding: 6px 14px; background: #1a73e8; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
    #sync-btn:disabled { background: #ccc; cursor: not-allowed; }
    #last-sync { font-size: 12px; color: #999; margin-top: 4px; }
    main { max-width: 1000px; margin: 24px auto; padding: 0 16px; }
    section { background: white; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    .section-header { padding: 14px 20px; font-size: 15px; font-weight: 600; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
    table { width: 100%; border-collapse: collapse; }
    th { text-align: left; padding: 10px 16px; font-size: 12px; color: #888; font-weight: 500; border-bottom: 1px solid #eee; }
    td { padding: 10px 16px; font-size: 14px; border-bottom: 1px solid #f5f5f5; vertical-align: middle; }
    tr:last-child td { border-bottom: none; }
    tr.fading { transition: opacity 0.3s; opacity: 0; }
    .diff-Easy { color: #00b8a3; }
    .diff-Medium { color: #e5a000; }
    .diff-Hard { color: #ff375f; }
    .overdue { color: #ff4d4f; }
    .rating-btn { padding: 3px 9px; margin-right: 4px; border-radius: 4px; cursor: pointer; font-size: 12px; background: white; }
    .rating-btn[data-r="Again"] { border: 1px solid #ff4d4f; color: #ff4d4f; }
    .rating-btn[data-r="Hard"]  { border: 1px solid #e5a000; color: #a06800; }
    .rating-btn[data-r="Good"]  { border: 1px solid #1a73e8; color: #1a73e8; }
    .rating-btn[data-r="Easy"]  { border: 1px solid #00b8a3; color: #00b8a3; }
    .rating-btn:hover { filter: brightness(0.92); }
    a { color: inherit; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .empty { padding: 36px; text-align: center; color: #aaa; font-size: 14px; }
    #future-content { display: none; }
  </style>
</head>
<body>
  <div id="banner"></div>
  <header>
    <div>
      <h1>LeetCode Review</h1>
      <div id="stats">加载中...</div>
    </div>
    <div class="header-right">
      <button id="sync-btn" onclick="syncNow()">立即同步</button>
      <div id="last-sync"></div>
    </div>
  </header>
  <main>
    <section>
      <div class="section-header">
        <span>今日待复习</span>
        <span id="due-count" style="font-weight:400;color:#888;font-size:13px;"></span>
      </div>
      <table>
        <thead><tr>
          <th>题号</th><th>题目</th><th>难度</th><th>到期日</th><th>逾期/今天</th><th>掌握度</th>
        </tr></thead>
        <tbody id="due-body"></tbody>
      </table>
    </section>
    <section>
      <div class="section-header" onclick="toggleFuture()">
        <span>未来计划</span>
        <span id="future-toggle" style="font-weight:400;color:#888;font-size:13px;">▶ 展开</span>
      </div>
      <div id="future-content">
        <table>
          <thead><tr>
            <th>题号</th><th>题目</th><th>难度</th><th>下次复习</th><th>剩余天数</th>
          </tr></thead>
          <tbody id="future-body"></tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    let dueTotal = 0;
    let doneCount = 0;
    let todayDate = null;

    function daysFromToday(isoStr) {
      return Math.round((new Date(isoStr) - todayDate) / 86400000);
    }

    function diffClass(d) {
      return "diff-" + d;
    }

    function updateStats() {
      const remaining = dueTotal - doneCount;
      document.getElementById("stats").textContent =
        `今日待复习 ${dueTotal} 题，已完成 ${doneCount} 题`;
      document.getElementById("due-count").textContent =
        remaining > 0 ? `${remaining} 题待完成` : "全部完成 🎉";
    }

    function renderDue(rows) {
      dueTotal = rows.length;
      updateStats();
      const tbody = document.getElementById("due-body");
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty">今日无待复习题目，保持！</td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map(r => {
        const diff = daysFromToday(r.due_date);
        const overdueStr = diff >= 0
          ? `<span style="color:#52c41a">今天</span>`
          : `<span class="overdue">${-diff} 天前</span>`;
        const ratings = ["Again", "Hard", "Good", "Easy"];
        const btns = ratings.map(rt =>
          `<button class="rating-btn" data-r="${rt}" onclick="rate('${r.problem_id}','${rt}')">${rt}</button>`
        ).join("");
        return `<tr id="row-${r.problem_id}">
          <td style="color:#999;font-size:12px;">${r.number}</td>
          <td><a href="${r.url}" target="_blank">${r.title}</a></td>
          <td class="${diffClass(r.difficulty)}">${r.difficulty}</td>
          <td style="color:#999;font-size:13px;">${r.due_date}</td>
          <td>${overdueStr}</td>
          <td>${btns}</td>
        </tr>`;
      }).join("");
    }

    function renderFuture(rows) {
      const toggle = document.getElementById("future-toggle");
      toggle.textContent = rows.length ? `▶ ${rows.length} 题` : "▶ 无";
      const tbody = document.getElementById("future-body");
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty">暂无未来计划</td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map(r => {
        const diff = daysFromToday(r.due_date);
        return `<tr>
          <td style="color:#999;font-size:12px;">${r.number}</td>
          <td><a href="${r.url}" target="_blank">${r.title}</a></td>
          <td class="${diffClass(r.difficulty)}">${r.difficulty}</td>
          <td style="color:#999;font-size:13px;">${r.due_date}</td>
          <td style="color:#999;font-size:13px;">${diff} 天后</td>
        </tr>`;
      }).join("");
    }

    async function load() {
      const res = await fetch("/api/reviews");
      const data = await res.json();
      todayDate = new Date(data.today);
      renderDue(data.due);
      renderFuture(data.future);
    }

    async function rate(problemId, rating) {
      const res = await fetch(`/api/review/${problemId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
      if (!res.ok) return;
      const row = document.getElementById(`row-${problemId}`);
      if (row) {
        row.classList.add("fading");
        setTimeout(() => row.remove(), 300);
      }
      doneCount++;
      updateStats();
    }

    async function syncNow() {
      const btn = document.getElementById("sync-btn");
      btn.disabled = true;
      btn.textContent = "同步中...";
      const res = await fetch("/api/sync", { method: "POST" });
      const data = await res.json();
      btn.disabled = false;
      btn.textContent = "立即同步";
      if (data.error) {
        const b = document.getElementById("banner");
        b.textContent = "⚠ " + data.error;
        b.style.display = "block";
      } else {
        document.getElementById("last-sync").textContent =
          `刚刚同步，新增 ${data.new_problems} 题`;
        doneCount = 0;
        load();
      }
    }

    function toggleFuture() {
      const content = document.getElementById("future-content");
      const toggle = document.getElementById("future-toggle");
      const isOpen = content.style.display === "block";
      content.style.display = isOpen ? "none" : "block";
      if (!isOpen) toggle.textContent = toggle.textContent.replace("▶", "▼");
      else toggle.textContent = toggle.textContent.replace("▼", "▶");
    }

    load();
  </script>
</body>
</html>
```

- [ ] **Step 3: Start the app and do a visual smoke test**

```bash
uv run python app.py
```

Open `http://localhost:5000`. Verify:
- Page renders without console errors
- "今日待复习 0 题，已完成 0 题" in header
- "今日无待复习题目" in due section
- 未来计划 section collapses/expands on click

Stop the server with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: single-page table UI with SM-2 rating buttons"
```

---

### Task 7: macOS LaunchAgent Installer

**Files:**
- Create: `install.py`

- [ ] **Step 1: Create install.py**

```python
import argparse
import os
import shutil
import subprocess
import sys
import textwrap

PLIST_LABEL = "com.leetcode-review"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")


def install():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(project_dir, "app.py")
    log_dir = os.path.expanduser("~/Library/Logs/leetcode-review")
    os.makedirs(log_dir, exist_ok=True)

    uv = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
    if not os.path.exists(uv):
        print("Error: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)

    plist = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>Label</key>
          <string>{PLIST_LABEL}</string>
          <key>ProgramArguments</key>
          <array>
            <string>{uv}</string>
            <string>run</string>
            <string>python</string>
            <string>{app_path}</string>
          </array>
          <key>WorkingDirectory</key>
          <string>{project_dir}</string>
          <key>RunAtLoad</key>
          <true/>
          <key>KeepAlive</key>
          <true/>
          <key>StandardOutPath</key>
          <string>{log_dir}/stdout.log</string>
          <key>StandardErrorPath</key>
          <string>{log_dir}/stderr.log</string>
        </dict>
        </plist>
    """)

    with open(PLIST_PATH, "w") as f:
        f.write(plist)

    subprocess.run(["launchctl", "load", PLIST_PATH], check=True)
    print("Installed. Flask will auto-start on login.")
    print(f"  Open: http://localhost:5000")
    print(f"  Logs: {log_dir}/")


def uninstall():
    if os.path.exists(PLIST_PATH):
        subprocess.run(["launchctl", "unload", PLIST_PATH])
        os.remove(PLIST_PATH)
        print("Uninstalled.")
    else:
        print("Not installed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeetCode Review LaunchAgent installer")
    parser.add_argument("--uninstall", action="store_true", help="Remove the LaunchAgent")
    args = parser.parse_args()
    uninstall() if args.uninstall else install()
```

- [ ] **Step 2: Verify the script parses correctly**

```bash
uv run python install.py --help
```

Expected output:
```
usage: install.py [-h] [--uninstall]

LeetCode Review LaunchAgent installer

options:
  -h, --help   show this help message and exit
  --uninstall  Remove the LaunchAgent
```

- [ ] **Step 3: Commit**

```bash
git add install.py
git commit -m "feat: macOS LaunchAgent installer and uninstaller"
```

---

### Task 8: Full Test Suite and Setup Verification

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All tests across `test_sm2.py`, `test_db.py`, `test_lc_client.py`, `test_app.py` PASS with no failures.

- [ ] **Step 2: Configure your LEETCODE_SESSION**

Edit `config.py`, replace the empty string:

```python
LEETCODE_SESSION = "paste_your_session_cookie_value_here"
```

To get the value: log in at leetcode.com → DevTools (F12) → Application → Cookies → `https://leetcode.com` → copy the `LEETCODE_SESSION` Value.

- [ ] **Step 3: Initialize the database and do a full sync**

```bash
uv run python -c "import db; db.init_db(); print('DB initialized')"
uv run python app.py &
curl -s -X POST http://localhost:5000/api/sync | python -m json.tool
```

Expected: JSON with `new_problems > 0` and `error: null`.

- [ ] **Step 4: Open the browser and verify**

Open `http://localhost:5000`. Confirm:
- Your solved problems appear in the due/future table
- Problem titles are clickable links to leetcode.com
- Clicking a rating button fades out the row and updates the counter
- 未来计划 section shows problems not yet due

- [ ] **Step 5: Install as LaunchAgent**

```bash
kill %1  # stop the background server from step 3
uv run python install.py
```

Expected: "Installed. Flask will auto-start on login." Open `http://localhost:5000` to confirm it's running.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: complete implementation verified"
```
