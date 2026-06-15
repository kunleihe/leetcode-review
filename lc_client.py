import time
import requests

GRAPHQL_URL = "https://leetcode.com/graphql"

_MAX_RETRIES = 3
_RETRY_BACKOFF = [2, 5, 10]  # seconds between retries


class AuthError(Exception):
    pass


def _headers(session):
    return {
        "Cookie": f"LEETCODE_SESSION={session}",
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }


def _post(payload, session):
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        resp = requests.post(GRAPHQL_URL, json=payload, headers=_headers(session))
        if resp.status_code in (401, 403):
            raise AuthError("LeetCode session cookie is invalid or expired.")
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = _RETRY_BACKOFF[attempt]
            time.sleep(wait)
            last_exc = requests.HTTPError(response=resp)
            continue
        resp.raise_for_status()
        # LeetCode occasionally returns 200 with a rate-limit error in the body
        body = resp.json()
        if "errors" in body:
            msgs = [e.get("message", "") for e in body["errors"]]
            if any("rate" in m.lower() or "limit" in m.lower() for m in msgs):
                wait = _RETRY_BACKOFF[attempt]
                time.sleep(wait)
                last_exc = RuntimeError(f"GraphQL rate limit: {msgs}")
                continue
        return resp
    if last_exc:
        raise last_exc
    raise RuntimeError("Max retries exceeded")


def _parse(resp):
    body = resp.json()
    if "errors" in body:
        raise RuntimeError(f"GraphQL error: {body['errors']}")
    return body["data"]


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


def iter_submissions(session, since_ts=0, delay=0.3):
    """
    Generator: yields one list of submissions per page (all statuses).
    Each yielded list contains only submissions after since_ts,
    deduplicated within this sync run (most recent submission per slug).
    Stops when: no more pages or oldest submission on a page predates since_ts.
    Deduplication against already-synced problems is handled by the caller.
    """
    offset = 0
    limit = 20
    seen_slugs = set()

    while True:
        payload = {
            "query": _SUBMISSION_LIST_QUERY,
            "variables": {"offset": offset, "limit": limit},
        }
        data = _parse(_post(payload, session))["submissionList"]
        submissions = data["submissions"] or []

        page_subs = []
        for sub in submissions:
            ts = int(sub["timestamp"])
            if ts < since_ts:
                continue
            slug = sub["titleSlug"]
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                page_subs.append(sub)

        if page_subs:
            yield page_subs

        if not data["hasNext"]:
            break
        if submissions and int(submissions[-1]["timestamp"]) < since_ts:
            break

        offset += limit
        time.sleep(delay)


def fetch_question_info(slug, session, delay=0.2):
    payload = {"query": _QUESTION_INFO_QUERY, "variables": {"titleSlug": slug}}
    q = _parse(_post(payload, session))["question"]
    time.sleep(delay)
    if not q:
        return {"number": 0, "difficulty": "Unknown"}
    return {"number": q["questionFrontendId"], "difficulty": q["difficulty"]}
