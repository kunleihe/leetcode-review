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
