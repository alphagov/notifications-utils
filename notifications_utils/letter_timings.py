from collections import namedtuple
from datetime import datetime, time, timedelta

import pytz

from notifications_utils.bank_holidays import BankHolidays
from notifications_utils.countries.data import Postage
from notifications_utils.timezones import (
    convert_utc_to_bst,
    utc_string_to_aware_gmt_datetime,
)

LETTER_PROCESSING_DEADLINE = time(17, 30)
CANCELLABLE_JOB_LETTER_STATUSES = [
    "created",
    "cancelled",
    "virus-scan-failed",
    "validation-failed",
    "technical-failure",
    "pending-virus-check",
]


non_working_days_dvla = BankHolidays(
    use_cached_holidays=True,
    weekend=(5, 6),
)
non_working_days_royal_mail = BankHolidays(
    use_cached_holidays=True,
    weekend=(6,),  # Only Sunday (day 6 of the week) is a non-working day
)


def is_dvla_working_day(datetime_object):
    return non_working_days_dvla.is_work_day(
        datetime_object.date(),
        division=BankHolidays.ENGLAND_AND_WALES,
    )


def is_royal_mail_working_day(datetime_object):
    return non_working_days_royal_mail.is_work_day(
        datetime_object.date(),
        division=BankHolidays.ENGLAND_AND_WALES,
    )


def set_gmt_hour(day, hour):
    return day.astimezone(pytz.timezone("Europe/London")).replace(hour=hour, minute=0).astimezone(pytz.utc)


def get_offset_working_day(date, *, is_work_day, days):
    if days > 0:
        step = 1
    elif days < 0:
        step = -1
    else:
        raise ValueError("days argument must not be 0")

    while days:
        date = date + timedelta(days=step)
        if is_work_day(date):
            days -= step

    return date


def get_dvla_working_day_offset_by(date, *, days):
    return get_offset_working_day(date, is_work_day=is_dvla_working_day, days=days)


def get_next_dvla_working_day(date):
    """
    Printing takes place monday to friday, excluding bank holidays
    """
    return get_dvla_working_day_offset_by(date, days=1)


def get_previous_dvla_working_day(date):
    return get_dvla_working_day_offset_by(date, days=-1)


def get_royal_mail_working_day_offset_by(date, *, days):
    return get_offset_working_day(date, is_work_day=is_royal_mail_working_day, days=days)


def get_next_royal_mail_working_day(date):
    """
    Royal mail deliver letters on monday to saturday
    """
    return get_royal_mail_working_day_offset_by(date, days=1)


def get_previous_royal_mail_working_day(date):
    return get_royal_mail_working_day_offset_by(date, days=-1)


def get_delivery_day(date, *, days_to_deliver):
    next_day = get_next_royal_mail_working_day(date)
    if days_to_deliver == 1:
        return next_day
    return get_delivery_day(next_day, days_to_deliver=(days_to_deliver - 1))


def get_min_and_max_days_in_transit(postage):
    return {
        # first class post is printed earlier in the day, so will
        # actually transit on the printing day, and be delivered the next
        # day, so effectively spends no full days in transit
        "first": (0, 0),
        "second": (1, 2),
        Postage.EUROPE: (3, 5),
        Postage.REST_OF_WORLD: (5, 7),
    }[postage]


def get_earliest_and_latest_delivery(print_day, postage):
    for days_to_transit in get_min_and_max_days_in_transit(postage):
        yield get_delivery_day(print_day, days_to_deliver=1 + days_to_transit)


def get_letter_timings(upload_time, postage):
    LetterTimings = namedtuple("LetterTimings", "printed_by, is_printed, earliest_delivery, latest_delivery")

    # shift anything after 5:30pm to the next day
    processing_day = utc_string_to_aware_gmt_datetime(upload_time) + timedelta(hours=6, minutes=30)
    print_day = get_next_dvla_working_day(processing_day)

    earliest_delivery, latest_delivery = get_earliest_and_latest_delivery(print_day, postage)

    # print deadline is 3pm BST
    printed_by = set_gmt_hour(print_day, hour=15)
    now = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone("Europe/London"))

    return LetterTimings(
        printed_by=printed_by,
        is_printed=(now > printed_by),
        earliest_delivery=set_gmt_hour(earliest_delivery, hour=16),
        latest_delivery=set_gmt_hour(latest_delivery, hour=16),
    )


def letter_can_be_cancelled(notification_status, notification_created_at):
    """
    If letter does not have status of created or pending-virus-check
        => can't be cancelled (it has already been processed)

    If it's after 5.30pm local time and the notification was created today before 5.30pm local time
        => can't be cancelled (it will already be zipped up to be sent)
    """
    if notification_status not in ("created", "pending-virus-check"):
        return False

    if too_late_to_cancel_letter(notification_created_at):
        return False
    return True


def too_late_to_cancel_letter(notification_created_at):
    time_created_at = convert_utc_to_bst(notification_created_at)
    day_created_on = time_created_at.date()

    current_time = convert_utc_to_bst(datetime.utcnow())
    current_day = current_time.date()
    if _after_letter_processing_deadline() and _notification_created_before_today_deadline(notification_created_at):
        return True
    if _notification_created_before_that_day_deadline(notification_created_at) and day_created_on < current_day:
        return True
    if (current_day - day_created_on).days > 1:
        return True


def _after_letter_processing_deadline():
    current_utc_datetime = datetime.utcnow()
    bst_time = convert_utc_to_bst(current_utc_datetime).time()

    return bst_time >= LETTER_PROCESSING_DEADLINE


def _notification_created_before_today_deadline(notification_created_at):
    current_bst_datetime = convert_utc_to_bst(datetime.utcnow())
    todays_deadline = current_bst_datetime.replace(
        hour=LETTER_PROCESSING_DEADLINE.hour,
        minute=LETTER_PROCESSING_DEADLINE.minute,
    )

    notification_created_at_in_bst = convert_utc_to_bst(notification_created_at)

    return notification_created_at_in_bst <= todays_deadline


def _notification_created_before_that_day_deadline(notification_created_at):
    notification_created_at_bst_datetime = convert_utc_to_bst(notification_created_at)
    created_at_day_deadline = notification_created_at_bst_datetime.replace(
        hour=LETTER_PROCESSING_DEADLINE.hour,
        minute=LETTER_PROCESSING_DEADLINE.minute,
    )

    return notification_created_at_bst_datetime <= created_at_day_deadline
