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


def collect(gen):
    """Flatten generator of pages into a single list."""
    return [sub for page in gen for sub in page]


def test_fetch_includes_all_statuses():
    with patch("lc_client.requests.post", return_value=mock_resp(MOCK_SUB_PAGE)):
        result = collect(lc_client.iter_submissions(session="fake", since_ts=0, delay=0))
    slugs = [r["titleSlug"] for r in result]
    assert "two-sum" in slugs
    assert "add-two-numbers" in slugs


def test_fetch_deduplicates_same_slug():
    with patch("lc_client.requests.post", return_value=mock_resp(MOCK_SUB_PAGE)):
        result = collect(lc_client.iter_submissions(session="fake", since_ts=0, delay=0))
    assert len([r for r in result if r["titleSlug"] == "two-sum"]) == 1


def test_fetch_filters_by_since_ts():
    with patch("lc_client.requests.post", return_value=mock_resp(MOCK_SUB_PAGE)):
        result = collect(lc_client.iter_submissions(session="fake", since_ts=1700050000, delay=0))
    slugs = [r["titleSlug"] for r in result]
    assert "two-sum" not in slugs
    assert "add-two-numbers" in slugs


def test_fetch_raises_auth_error_on_403():
    with patch("lc_client.requests.post", return_value=mock_resp({}, status=403)):
        with pytest.raises(lc_client.AuthError):
            collect(lc_client.iter_submissions(session="bad", since_ts=0, delay=0))


def test_fetch_question_info():
    with patch("lc_client.requests.post", return_value=mock_resp(MOCK_QUESTION)):
        info = lc_client.fetch_question_info("two-sum", session="fake", delay=0)
    assert info["difficulty"] == "Easy"
    assert info["number"] == "1"


def test_fetch_raises_on_graphql_error():
    error_resp = {"errors": [{"message": "Unauthorized"}]}
    with patch("lc_client.requests.post", return_value=mock_resp(error_resp)):
        with pytest.raises(RuntimeError, match="GraphQL error"):
            collect(lc_client.iter_submissions(session="fake", since_ts=0, delay=0))
