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
    resp.raise_for_status()
    return resp


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


def fetch_ac_submissions(session, since_ts=0, delay=0.5):
    offset = 0
    limit = 20
    seen = {}  # slug -> earliest AC submission dict

    while True:
        payload = {
            "query": _SUBMISSION_LIST_QUERY,
            "variables": {"offset": offset, "limit": limit},
        }
        data = _parse(_post(payload, session))["submissionList"]
        submissions = data["submissions"]

        for sub in submissions:
            if sub["statusDisplay"] != "Accepted":
                continue
            ts = int(sub["timestamp"])
            if ts < since_ts:
                continue
            slug = sub["titleSlug"]
            if slug not in seen or ts < int(seen[slug]["timestamp"]):
                seen[slug] = sub

        # Stop if no more pages or if oldest entry on page is before our cutoff
        if not data["hasNext"]:
            break
        if submissions and int(submissions[-1]["timestamp"]) < since_ts:
            break

        offset += limit
        time.sleep(delay)

    return list(seen.values())


def fetch_question_info(slug, session, delay=0.3):
    payload = {"query": _QUESTION_INFO_QUERY, "variables": {"titleSlug": slug}}
    q = _parse(_post(payload, session))["question"]
    time.sleep(delay)
    return {"number": q["questionFrontendId"], "difficulty": q["difficulty"]}
