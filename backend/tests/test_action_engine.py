"""Tests for the action card rules engine and date helpers."""

from datetime import date, timedelta

from app.utils.date_helpers import days_until, human_time_description, urgency_level


def test_days_until_future():
    future = date.today() + timedelta(days=5)
    assert days_until(future) == 5


def test_days_until_past():
    past = date.today() - timedelta(days=3)
    assert days_until(past) == -3


def test_days_until_none():
    assert days_until(None) is None


def test_urgency_high():
    assert urgency_level(1) == "high"
    assert urgency_level(3) == "high"


def test_urgency_medium():
    assert urgency_level(5) == "medium"
    assert urgency_level(14) == "medium"


def test_urgency_low():
    assert urgency_level(15) == "low"
    assert urgency_level(30) == "low"


def test_urgency_none():
    assert urgency_level(None) == "low"


def test_human_time_today():
    assert human_time_description(0) == "today"


def test_human_time_tomorrow():
    assert human_time_description(1) == "tomorrow"


def test_human_time_days():
    assert human_time_description(5) == "in 5 days"


def test_human_time_past():
    assert human_time_description(-3) == "3 days ago"


def test_human_time_weeks():
    assert human_time_description(35) == "in 5 weeks"
