from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


LOCAL_TIMEZONE = ZoneInfo("America/Chicago")

STUDY_START = time(8, 0)
STUDY_END = time(22, 0)
MIN_SESSION_MINUTES = 30


def merge_busy_periods(busy_intervals):
    """Merge overlapping or consecutive calendar commitments."""

    if not busy_intervals:
        return []

    busy_intervals.sort()
    merged = [busy_intervals[0]]

    for start, end in busy_intervals[1:]:
        last_start, last_end = merged[-1]

        if start <= last_end:
            merged[-1] = (
                last_start,
                max(last_end, end),
            )
        else:
            merged.append((start, end))

    return merged


def find_available_slots(busy_periods, days=7):
    """Find available study times outside calendar commitments."""

    now = datetime.now(LOCAL_TIMEZONE)
    available_slots = []
    busy_intervals = []

    # Convert Google Calendar busy periods to local time.
    for period in busy_periods:
        start = datetime.fromisoformat(
            period["start"].replace("Z", "+00:00")
        ).astimezone(LOCAL_TIMEZONE)

        end = datetime.fromisoformat(
            period["end"].replace("Z", "+00:00")
        ).astimezone(LOCAL_TIMEZONE)

        # Ignore invalid or zero-length commitments.
        if end <= start:
            continue

        busy_intervals.append((start, end))

    # Merge overlapping commitments.
    busy_intervals = merge_busy_periods(busy_intervals)

    # Check each day in the scheduling window.
    for day_offset in range(days):

        current_date = (
            now + timedelta(days=day_offset)
        ).date()

        day_start = datetime.combine(
            current_date,
            STUDY_START,
            tzinfo=LOCAL_TIMEZONE,
        )

        day_end = datetime.combine(
            current_date,
            STUDY_END,
            tzinfo=LOCAL_TIMEZONE,
        )

        # Exclude study times that have already passed.
        current_start = max(day_start, now)

        for busy_start, busy_end in busy_intervals:

            # Skip commitments outside the current day.
            if busy_end <= current_start or busy_start >= day_end:
                continue

            free_end = min(busy_start, day_end)

            # Save free time before the next commitment.
            if (
                free_end - current_start
            ).total_seconds() >= MIN_SESSION_MINUTES * 60:

                available_slots.append({
                    "start": current_start.isoformat(),
                    "end": free_end.isoformat(),
                })

            current_start = max(current_start, busy_end)

            if current_start >= day_end:
                break

        # Save remaining free time after commitments.
        if (
            day_end - current_start
        ).total_seconds() >= MIN_SESSION_MINUTES * 60:

            available_slots.append({
                "start": current_start.isoformat(),
                "end": day_end.isoformat(),
            })

    return available_slots