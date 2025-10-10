from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from dateutil import parser

local_timezone = ZoneInfo("Europe/London")


def utc_string_to_aware_gmt_datetime(date):
    """
    Date can either be a string, naive UTC datetime or an aware UTC datetime
    Returns an aware London datetime, essentially the time you'd see on your clock
    """
    if not isinstance(date, datetime):
        date = parser.parse(date)

    forced_utc = date.replace(tzinfo=UTC)
    return forced_utc.astimezone(local_timezone)


def convert_utc_to_bst(utc_dt):
    """
    Takes a naive UTC datetime and returns a naive London datetime
    """
    return utc_dt.replace(tzinfo=UTC).astimezone(local_timezone).replace(tzinfo=None)


def convert_bst_to_utc(date):
    """
    Takes a naive London datetime and returns a naive UTC datetime
    """
    return date.replace(tzinfo=local_timezone).astimezone(UTC).replace(tzinfo=None)
