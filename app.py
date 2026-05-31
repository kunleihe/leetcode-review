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
db.init_db()


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
    result = run_sync()
    if result["error"]:
        status = 401 if "session" in result["error"].lower() else 500
        return jsonify(result), status
    return jsonify(result)


if __name__ == "__main__":
    db.init_db()
    app.run(port=config.PORT, debug=False)
