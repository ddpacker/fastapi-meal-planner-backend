from datetime import date, datetime, timedelta, timezone


MAX_WEEKS_AHEAD = 4


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def monday_of_week(day: date) -> date:
    return day - timedelta(days=day.weekday())


def max_start_monday(today: date | None = None) -> date:
    current = monday_of_week(today or utc_today())
    return current + timedelta(weeks=MAX_WEEKS_AHEAD)


def validate_meal_plan_week_dates(
    start_date: date,
    end_date: date,
    *,
    today: date | None = None,
) -> None:
    """Raise ValueError with a client-facing message when week dates are invalid."""
    today = today or utc_today()
    current_monday = monday_of_week(today)
    if start_date.weekday() != 0:
        raise ValueError("start_date must be a Monday")
    if end_date != start_date + timedelta(days=6):
        raise ValueError("end_date must be start_date plus 6 days (Sunday)")
    if start_date < current_monday:
        raise ValueError("start_date cannot be before the current week")
    if start_date > max_start_monday(today):
        raise ValueError(
            f"start_date cannot be more than {MAX_WEEKS_AHEAD} weeks ahead"
        )
