from collections import namedtuple
from datetime import UTC, datetime, time, timedelta

from notifications_utils.bank_holidays import BankHolidays
from notifications_utils.countries.data import Postage
from notifications_utils.timezones import (
    local_timezone,
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
non_working_days_royal_mail_first_class = BankHolidays(
    use_cached_holidays=True,
    weekend=(6,),  # Only Sunday (day 6 of the week) is a non-working day for first class mail
)
non_working_days_royal_mail_default = BankHolidays(
    use_cached_holidays=True,
    weekend=(5, 6),  # Saturday and Sunday are non-working days
)


def is_dvla_working_day(datetime_object):
    return non_working_days_dvla.is_work_day(
        datetime_object.date(),
        division=BankHolidays.ENGLAND_AND_WALES,
    )


def is_royal_mail_working_day_first_class(datetime_object):
    return non_working_days_royal_mail_first_class.is_work_day(
        datetime_object.date(),
        division=BankHolidays.ENGLAND_AND_WALES,
    )


def is_royal_mail_working_day_default(datetime_object):
    return non_working_days_royal_mail_default.is_work_day(
        datetime_object.date(),
        division=BankHolidays.ENGLAND_AND_WALES,
    )


def set_gmt_hour(day, hour):
    return day.astimezone(local_timezone).replace(hour=hour, minute=0).astimezone(UTC)


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


def get_royal_mail_working_day_offset_by(date, *, days, postage):
    """
    Royal mail deliver letters on Monday to Friday, with deliveries also taking place on Saturday
    for First class mail
    """
    if postage == Postage.FIRST:
        is_work_day = is_royal_mail_working_day_first_class
    else:
        is_work_day = is_royal_mail_working_day_default

    return get_offset_working_day(date, is_work_day=is_work_day, days=days)


def get_next_royal_mail_working_day(date, postage):
    return get_royal_mail_working_day_offset_by(date, days=1, postage=postage)


def get_previous_royal_mail_working_day(date, postage):
    return get_royal_mail_working_day_offset_by(date, days=-1, postage=postage)


def get_delivery_day(date, *, days_to_deliver, postage):
    next_day = get_next_royal_mail_working_day(date, postage)
    if days_to_deliver == 1:
        return next_day
    return get_delivery_day(next_day, days_to_deliver=(days_to_deliver - 1), postage=postage)


def get_min_and_max_days_in_transit(postage):
    return {
        # first class post is printed earlier in the day, so will
        # actually transit on the printing day, and be delivered the next
        # day, so effectively spends no full days in transit
        Postage.FIRST: (0, 0),
        Postage.SECOND: (3, 4),
        Postage.ECONOMY: (3, 6),
        Postage.EUROPE: (3, 5),
        Postage.REST_OF_WORLD: (5, 7),
    }[postage]


def get_earliest_and_latest_delivery(print_day, postage):
    for days_to_transit in get_min_and_max_days_in_transit(postage):
        yield get_delivery_day(print_day, days_to_deliver=1 + days_to_transit, postage=postage)


def get_letter_timings(upload_time, postage):
    LetterTimings = namedtuple("LetterTimings", "printed_by, is_printed, earliest_delivery, latest_delivery")

    # shift anything after 5:30pm to the next day
    processing_day = utc_string_to_aware_gmt_datetime(upload_time) + timedelta(hours=6, minutes=30)
    print_day = get_next_dvla_working_day(processing_day)

    earliest_delivery, latest_delivery = get_earliest_and_latest_delivery(print_day, postage)

    # print deadline is 3pm BST
    printed_by = set_gmt_hour(print_day, hour=15)
    now = datetime.now(local_timezone)

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
    day_created_on = utc_string_to_aware_gmt_datetime(notification_created_at).date()

    current_day = datetime.now(local_timezone).date()
    if _after_letter_processing_deadline() and _notification_created_before_today_deadline(notification_created_at):
        return True
    if _notification_created_before_that_day_deadline(notification_created_at) and day_created_on < current_day:
        return True
    if (current_day - day_created_on).days > 1:
        return True


def _after_letter_processing_deadline():
    return datetime.now(local_timezone).time() >= LETTER_PROCESSING_DEADLINE


def _notification_created_before_today_deadline(notification_created_at):
    todays_deadline = datetime.now(local_timezone).replace(
        hour=LETTER_PROCESSING_DEADLINE.hour,
        minute=LETTER_PROCESSING_DEADLINE.minute,
    )
    return utc_string_to_aware_gmt_datetime(notification_created_at) <= todays_deadline


def _notification_created_before_that_day_deadline(notification_created_at):
    notification_created_at_bst_datetime = utc_string_to_aware_gmt_datetime(notification_created_at)
    created_at_day_deadline = notification_created_at_bst_datetime.replace(
        hour=LETTER_PROCESSING_DEADLINE.hour,
        minute=LETTER_PROCESSING_DEADLINE.minute,
    )

    return notification_created_at_bst_datetime <= created_at_day_deadline
