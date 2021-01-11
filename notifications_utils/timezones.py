from datetime import datetime

import pytz
from dateutil import parser

local_timezone = pytz.timezone("Europe/London")


def utc_string_to_aware_gmt_datetime(date):
    """
    Date can either be a string or a naive datetime
    """
    if not isinstance(date, datetime):
        date = parser.parse(date)

    forced_utc = date.replace(tzinfo=pytz.utc)
    return forced_utc.astimezone(local_timezone)


def convert_utc_to_bst(utc_dt):
    return pytz.utc.localize(utc_dt).astimezone(local_timezone).replace(tzinfo=None)


def convert_bst_to_utc(date):
    return local_timezone.localize(date).astimezone(pytz.UTC).replace(tzinfo=None)
