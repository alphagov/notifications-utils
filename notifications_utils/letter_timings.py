import pytz

from datetime import datetime, timedelta
from collections import namedtuple

from notifications_utils.timezones import utc_string_to_aware_gmt_datetime


def set_gmt_hour(day, hour):
    return day.astimezone(pytz.timezone('Europe/London')).replace(hour=hour, minute=0).astimezone(pytz.utc)


def get_letter_timings(upload_time):

    LetterTimings = namedtuple(
        'LetterTimings',
        'printed_by, is_printed, earliest_delivery, latest_delivery'
    )

    # shift anything after 5pm to the next day
    processing_day = utc_string_to_aware_gmt_datetime(upload_time) + timedelta(hours=(7))

    def next_monday(date):
        """
        If called with a monday, will still return the next monday
        """
        return date + timedelta(days=7 - date.weekday())

    def get_next_dvla_working_day(date):
        """
        Printing takes place monday to friday
        """
        # monday to thursday inclusive
        if 0 <= date.weekday() <= 3:
            return date + timedelta(days=1)
        else:
            return next_monday(date)

    def get_next_royal_mail_working_day(date):
        """
        Royal mail deliver letters on monday to saturday
        """
        # monday to friday inclusive
        if 0 <= date.weekday() <= 4:
            return date + timedelta(days=1)
        else:
            return next_monday(date)

    print_day = get_next_dvla_working_day(processing_day)

    # first class post is printed earlier in the day, so will be delivered on the transit day
    transit_day = get_next_royal_mail_working_day(print_day)
    # second class
    earliest_delivery = get_next_royal_mail_working_day(transit_day)
    latest_delivery = get_next_royal_mail_working_day(earliest_delivery)

    printed_by = set_gmt_hour(print_day, hour=15)
    now = datetime.utcnow().replace(tzinfo=pytz.timezone('Europe/London'))

    return LetterTimings(
        printed_by=printed_by,
        is_printed=(now > printed_by),
        earliest_delivery=set_gmt_hour(earliest_delivery, hour=16),
        latest_delivery=set_gmt_hour(latest_delivery, hour=16),
    )
