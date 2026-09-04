from datetime import date, timedelta

import pytest

from app.services.meal_plan_service import (
    monday_of_week,
    max_start_monday,
    validate_meal_plan_week_dates,
)


def test_monday_of_week_floors_to_monday() -> None:
    assert monday_of_week(date(2026, 9, 3)) == date(2026, 8, 31)  # Thursday
    assert monday_of_week(date(2026, 8, 31)) == date(2026, 8, 31)  # Monday
    assert monday_of_week(date(2026, 9, 6)) == date(2026, 8, 31)  # Sunday


def test_max_start_monday_is_four_weeks_ahead() -> None:
    assert max_start_monday(date(2026, 9, 3)) == date(2026, 9, 28)


def test_validate_accepts_current_and_max_ahead() -> None:
    today = date(2026, 9, 3)
    current = monday_of_week(today)
    validate_meal_plan_week_dates(current, current + timedelta(days=6), today=today)
    farthest = max_start_monday(today)
    validate_meal_plan_week_dates(farthest, farthest + timedelta(days=6), today=today)


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (date(2026, 9, 1), date(2026, 9, 7), "start_date must be a Monday"),
        (date(2026, 8, 31), date(2026, 9, 5), "end_date must be start_date plus 6 days"),
        (date(2026, 8, 24), date(2026, 8, 30), "start_date cannot be before the current week"),
        (
            date(2026, 10, 5),
            date(2026, 10, 11),
            "start_date cannot be more than 4 weeks ahead",
        ),
    ],
)
def test_validate_rejects_invalid_weeks(
    start: date, end: date, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_meal_plan_week_dates(start, end, today=date(2026, 9, 3))
