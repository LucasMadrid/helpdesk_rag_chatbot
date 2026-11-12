"""The sidebar's pure helpers: titles, ages and grouping by day."""

from datetime import UTC, datetime, timedelta
from uuid import uuid7

import pytest

from helpdesk_rag_chatbot.ui.backend import SessionInfo
from helpdesk_rag_chatbot.ui.sidebar import ago, group_by_day, short

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)


def _session(age: timedelta, title: str = "t") -> SessionInfo:
    return SessionInfo(uuid7(), title, NOW - age)


def test_short_keeps_a_fitting_title_and_cuts_a_long_one() -> None:
    assert short("hello", 22) == "hello"
    assert short("x" * 22, 22) == "x" * 22
    assert short("x" * 23, 22) == "x" * 21 + "…"


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(seconds=5), "1 min"),
        (timedelta(minutes=5), "5 min"),
        (timedelta(minutes=59), "59 min"),
        (timedelta(hours=3), "3 h"),
        (timedelta(days=2, hours=5), "2 d"),
    ],
)
def test_ago_is_a_compact_age(age: timedelta, expected: str) -> None:
    assert ago(NOW - age, now=NOW) == expected


def test_group_by_day_uses_labelled_buckets_and_keeps_the_order() -> None:
    today = _session(timedelta(minutes=5), "today")
    yesterday = _session(timedelta(days=1), "yesterday")
    this_week = _session(timedelta(days=4), "this week")
    older = _session(timedelta(days=30), "older")

    groups = group_by_day([today, yesterday, this_week, older], now=NOW)

    assert [(label, [s.title for s in sessions]) for label, sessions in groups] == [
        ("Today", ["today"]),
        ("Yesterday", ["yesterday"]),
        ("Previous 7 days", ["this week"]),
        ("Older", ["older"]),
    ]


def test_group_by_day_leaves_out_empty_groups() -> None:
    assert group_by_day([], now=NOW) == []
    [(label, _)] = group_by_day([_session(timedelta(days=30))], now=NOW)
    assert label == "Older"
