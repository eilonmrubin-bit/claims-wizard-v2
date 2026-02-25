"""Stage 3.5: Day Segments Computation.

Fills day_segments in daily_records based on the weekly rest window.
Runs after stage 3 (week classification) and before stage 4 (threshold resolution).

Each calendar day is split into segments:
- regular: Normal work hours
- eve_of_rest: The evening portion before rest day starts (from candle lighting)
- rest: The rest day itself (until havdalah)
"""

from datetime import date, time, timedelta
from collections import defaultdict

from ...ssot import DailyRecord, DaySegment, DaySegmentType, RestDay, District
from .shabbat_times import get_shabbat_times_range, ShabbatTime


def compute_day_segments(
    daily_records: list[DailyRecord],
    rest_day: RestDay,
    district: District,
) -> list[DailyRecord]:
    """Compute day_segments for all daily records.

    For each day, determines which portions are:
    - regular: Not within rest window
    - eve_of_rest: From rest window start (candle lighting) to midnight on eve day
    - rest: The rest day itself (midnight to midnight or until havdalah)

    Args:
        daily_records: List of daily records from weaver
        rest_day: Employee's rest day (Saturday, Friday, Sunday)
        district: Employee's district (for Shabbat times lookup)

    Returns:
        daily_records with day_segments filled
    """
    if not daily_records:
        return daily_records

    # Get date range
    all_dates = [dr.date for dr in daily_records]
    start_date = min(all_dates)
    end_date = max(all_dates)

    # Load Shabbat times if Saturday rest
    shabbat_times: dict[date, ShabbatTime] = {}
    if rest_day == RestDay.SATURDAY:
        shabbat_times = get_shabbat_times_range(start_date, end_date, district)

    # Process each daily record
    for dr in daily_records:
        dr.day_segments = _compute_segments_for_day(
            dr.date,
            rest_day,
            shabbat_times,
        )

    return daily_records


def _compute_segments_for_day(
    day: date,
    rest_day: RestDay,
    shabbat_times: dict[date, ShabbatTime],
) -> list[DaySegment]:
    """Compute segments for a single day.

    Returns list of DaySegment covering 00:00-24:00.
    """
    day_start = time(0, 0)
    day_end = time(23, 59, 59)  # Represents 24:00

    if rest_day == RestDay.SATURDAY:
        return _segments_for_saturday_rest(day, shabbat_times)
    elif rest_day == RestDay.FRIDAY:
        return _segments_for_friday_rest(day)
    else:  # SUNDAY
        return _segments_for_sunday_rest(day)


def _segments_for_saturday_rest(
    day: date,
    shabbat_times: dict[date, ShabbatTime],
) -> list[DaySegment]:
    """Compute segments when rest day is Saturday.

    - Friday: regular until candles, eve_of_rest after candles
    - Saturday: rest all day (simplified - ignoring havdalah)
    - Other days: regular
    """
    dow = day.weekday()  # 0=Monday, 6=Sunday

    # Saturday (dow=5)
    if dow == 5:
        return [
            DaySegment(
                start=time(0, 0),
                end=time(23, 59, 59),
                type=DaySegmentType.REST,
            )
        ]

    # Friday (dow=4)
    if dow == 4:
        # Get candle lighting time for this Friday
        shabbat = shabbat_times.get(day)
        if shabbat and shabbat.candles:
            candle_time = shabbat.candles.time()

            # If candle time is after midnight (shouldn't happen but safe)
            if candle_time == time(0, 0):
                return [
                    DaySegment(
                        start=time(0, 0),
                        end=time(23, 59, 59),
                        type=DaySegmentType.EVE_OF_REST,
                    )
                ]

            segments = []

            # Before candles: regular
            if candle_time > time(0, 0):
                segments.append(
                    DaySegment(
                        start=time(0, 0),
                        end=candle_time,
                        type=DaySegmentType.REGULAR,
                    )
                )

            # After candles: eve_of_rest
            segments.append(
                DaySegment(
                    start=candle_time,
                    end=time(23, 59, 59),
                    type=DaySegmentType.EVE_OF_REST,
                )
            )

            return segments

        # Fallback: use default candle time (~17:30)
        default_candles = time(17, 30)
        return [
            DaySegment(
                start=time(0, 0),
                end=default_candles,
                type=DaySegmentType.REGULAR,
            ),
            DaySegment(
                start=default_candles,
                end=time(23, 59, 59),
                type=DaySegmentType.EVE_OF_REST,
            ),
        ]

    # Other days: all regular
    return [
        DaySegment(
            start=time(0, 0),
            end=time(23, 59, 59),
            type=DaySegmentType.REGULAR,
        )
    ]


def _segments_for_friday_rest(day: date) -> list[DaySegment]:
    """Compute segments when rest day is Friday.

    - Thursday: eve_of_rest (simplified - all day)
    - Friday: rest all day
    - Other days: regular
    """
    dow = day.weekday()  # 0=Monday, 6=Sunday

    # Friday (dow=4) = rest day
    if dow == 4:
        return [
            DaySegment(
                start=time(0, 0),
                end=time(23, 59, 59),
                type=DaySegmentType.REST,
            )
        ]

    # Thursday (dow=3) = eve of rest
    if dow == 3:
        return [
            DaySegment(
                start=time(0, 0),
                end=time(23, 59, 59),
                type=DaySegmentType.EVE_OF_REST,
            )
        ]

    # Other days: all regular
    return [
        DaySegment(
            start=time(0, 0),
            end=time(23, 59, 59),
            type=DaySegmentType.REGULAR,
        )
    ]


def _segments_for_sunday_rest(day: date) -> list[DaySegment]:
    """Compute segments when rest day is Sunday.

    - Saturday: eve_of_rest (simplified - all day)
    - Sunday: rest all day
    - Other days: regular
    """
    dow = day.weekday()  # 0=Monday, 6=Sunday

    # Sunday (dow=6) = rest day
    if dow == 6:
        return [
            DaySegment(
                start=time(0, 0),
                end=time(23, 59, 59),
                type=DaySegmentType.REST,
            )
        ]

    # Saturday (dow=5) = eve of rest
    if dow == 5:
        return [
            DaySegment(
                start=time(0, 0),
                end=time(23, 59, 59),
                type=DaySegmentType.EVE_OF_REST,
            )
        ]

    # Other days: all regular
    return [
        DaySegment(
            start=time(0, 0),
            end=time(23, 59, 59),
            type=DaySegmentType.REGULAR,
        )
    ]
