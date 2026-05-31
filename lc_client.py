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

        page_hit_cutoff = False
        for sub in data["submissions"]:
            ts = int(sub["timestamp"])
            if ts < since_ts:
                page_hit_cutoff = True
                continue
            if sub["statusDisplay"] != "Accepted":
                continue
            slug = sub["titleSlug"]
            if slug not in seen or ts < int(seen[slug]["timestamp"]):
                seen[slug] = sub

        if page_hit_cutoff or not data["hasNext"]:
            break

        offset += limit
        time.sleep(delay)

    return list(seen.values())


def fetch_question_info(slug, session, delay=0.3):
    payload = {"query": _QUESTION_INFO_QUERY, "variables": {"titleSlug": slug}}
    q = _post(payload, session).json()["data"]["question"]
    time.sleep(delay)
    return {"number": q["questionFrontendId"], "difficulty": q["difficulty"]}
