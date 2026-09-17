import logging
import threading
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
db.init_db()

_sync_lock = threading.Lock()
_sync_state = {"running": False, "new_problems": 0, "error": None}


def _run_sync_bg():
    global _sync_state
    session = config.get_leetcode_session()
    if not session:
        _sync_state = {"running": False, "new_problems": 0,
                       "error": "LEETCODE_SESSION not configured"}
        _sync_lock.release()
        return
    try:
        since_ts = db.get_latest_solved_ts() or 0
        initial = since_ts == 0
        limit = config.INITIAL_SYNC_LIMIT if initial else None
        count = 0
        done = False
        for page in lc_client.iter_submissions(
            session=session, since_ts=since_ts
        ):
            for sub in page:
                slug = sub["titleSlug"]
                if db.get_review(slug):
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
                _sync_state["new_problems"] = count
                if limit and count >= limit:
                    done = True
                    break
            if done:
                break
        db.log_sync(int(time.time()), count)
        _sync_state = {"running": False, "new_problems": count, "error": None}
    except lc_client.AuthError as e:
        _sync_state = {"running": False, "new_problems": 0, "error": str(e)}
    except Exception as e:
        log.exception("Sync failed")
        _sync_state = {"running": False, "new_problems": 0, "error": str(e)}
    finally:
        _sync_lock.release()


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
        "total_problems": db.count_problems(),
        "initial_sync_limit": config.INITIAL_SYNC_LIMIT,
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
    global _sync_state
    if not _sync_lock.acquire(blocking=False):
        return jsonify({"status": "already_running"})
    _sync_state = {"running": True, "new_problems": 0, "error": None}
    threading.Thread(target=_run_sync_bg, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/sync/status")
def api_sync_status():
    return jsonify(_sync_state)


if __name__ == "__main__":
    db.init_db()
    app.run(port=config.PORT, debug=False)
