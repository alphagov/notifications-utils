import pytz

from datetime import datetime, time, timedelta
from collections import namedtuple

from notifications_utils.timezones import convert_utc_to_bst, utc_string_to_aware_gmt_datetime


LETTER_PROCESSING_DEADLINE = time(17, 30)
CANCELLABLE_JOB_LETTER_STATUSES = [
    'created', 'cancelled', 'virus-scan-failed', 'validation-failed', 'technical-failure', 'pending-virus-check'
]


def set_gmt_hour(day, hour):
    return day.astimezone(pytz.timezone('Europe/London')).replace(hour=hour, minute=0).astimezone(pytz.utc)


def get_letter_timings(upload_time, postage='second'):

    LetterTimings = namedtuple(
        'LetterTimings',
        'printed_by, is_printed, earliest_delivery, latest_delivery'
    )

    # shift anything after 5:30pm to the next day
    processing_day = utc_string_to_aware_gmt_datetime(upload_time) + timedelta(hours=6, minutes=30)

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

    # first class post is printed earlier in the day, so will actually transit on the printing day,
    # and be posted the next day
    transit_day = get_next_royal_mail_working_day(print_day)
    if postage == 'first':
        earliest_delivery = latest_delivery = transit_day
    else:
        # second class has one day in transit, then a two day delivery window
        earliest_delivery = get_next_royal_mail_working_day(transit_day)
        latest_delivery = get_next_royal_mail_working_day(earliest_delivery)

    # print deadline is 3pm BST
    printed_by = set_gmt_hour(print_day, hour=15)
    now = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Europe/London'))

    return LetterTimings(
        printed_by=printed_by,
        is_printed=(now > printed_by),
        earliest_delivery=set_gmt_hour(earliest_delivery, hour=16),
        latest_delivery=set_gmt_hour(latest_delivery, hour=16),
    )


def letter_can_be_cancelled(notification_status, notification_created_at):
    '''
    If letter does not have status of created or pending-virus-check
        => can't be cancelled (it has already been processed)

    If it's after 5.30pm local time and the notification was created today before 5.30pm local time
        => can't be cancelled (it will already be zipped up to be sent)
    '''
    if notification_status not in ('created', 'pending-virus-check'):
        return False

    if _after_letter_processing_deadline() and _notification_created_before_today_deadline(notification_created_at):
        return False

    if _notification_created_before_that_day_deadline(
        notification_created_at
    ) and notification_created_at.date() < convert_utc_to_bst(datetime.utcnow()).date():
        return False
    if (convert_utc_to_bst(datetime.utcnow()).date() - notification_created_at.date()).days > 1:
        return False
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
