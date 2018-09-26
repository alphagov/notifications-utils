import pytest
import pytz

from freezegun import freeze_time
from notifications_utils.letter_timings import get_letter_timings


@freeze_time('2017-07-14 14:59:59')  # Friday, before print deadline
@pytest.mark.parametrize('upload_time, expected_print_time, is_printed, expected_earliest, expected_latest', [

    # BST
    # ==================================================================
    #  First thing Monday
    (
        'Monday 2017-07-10 00:00:01',
        'Tuesday 2017-07-11 15:00',
        True,
        'Thursday 2017-07-13 16:00',
        'Friday 2017-07-14 16:00'
    ),
    #  Monday at 16:59 BST
    (
        'Monday 2017-07-10 15:59:59',
        'Tuesday 2017-07-11 15:00',
        True,
        'Thursday 2017-07-13 16:00',
        'Friday 2017-07-14 16:00'
    ),
    #  Monday at 17:00 BST
    (
        'Monday 2017-07-10 16:00:01',
        'Wednesday 2017-07-12 15:00',
        True,
        'Friday 2017-07-14 16:00',
        'Saturday 2017-07-15 16:00'
    ),
    #  Tuesday before 17:00 BST
    (
        'Tuesday 2017-07-11 12:00:00',
        'Wednesday 2017-07-12 15:00',
        True,
        'Friday 2017-07-14 16:00',
        'Saturday 2017-07-15 16:00'
    ),
    #  Wednesday before 17:00 BST
    (
        'Wednesday 2017-07-12 12:00:00',
        'Thursday 2017-07-13 15:00',
        True,
        'Saturday 2017-07-15 16:00',
        'Monday 2017-07-17 16:00'
    ),
    #  Thursday before 17:00 BST
    (
        'Thursday 2017-07-13 12:00:00',
        'Friday 2017-07-14 15:00',
        True,  # WRONG
        'Monday 2017-07-17 16:00',
        'Tuesday 2017-07-18 16:00'
    ),
    #  Friday anytime
    (
        'Friday 2017-07-14 00:00:00',
        'Monday 2017-07-17 15:00',
        False,
        'Wednesday 2017-07-19 16:00',
        'Thursday 2017-07-20 16:00'
    ),
    (
        'Friday 2017-07-14 12:00:00',
        'Monday 2017-07-17 15:00',
        False,
        'Wednesday 2017-07-19 16:00',
        'Thursday 2017-07-20 16:00'
    ),
    (
        'Friday 2017-07-14 22:00:00',
        'Monday 2017-07-17 15:00',
        False,
        'Wednesday 2017-07-19 16:00',
        'Thursday 2017-07-20 16:00'
    ),
    #  Saturday anytime
    (
        'Saturday 2017-07-14 12:00:00',
        'Monday 2017-07-17 15:00',
        False,
        'Wednesday 2017-07-19 16:00',
        'Thursday 2017-07-20 16:00'
    ),
    #  Sunday before 1700 BST
    (
        'Sunday 2017-07-15 15:59:59',
        'Monday 2017-07-17 15:00',
        False,
        'Wednesday 2017-07-19 16:00',
        'Thursday 2017-07-20 16:00'
    ),
    #  Sunday after 17:00 BST
    (
        'Sunday 2017-07-16 16:00:01',
        'Tuesday 2017-07-18 15:00',
        False,
        'Thursday 2017-07-20 16:00',
        'Friday 2017-07-21 16:00'
    ),

    # GMT
    # ==================================================================
    #  Monday at 16:59 GMT
    (
        'Monday 2017-01-02 16:59:59',
        'Tuesday 2017-01-03 15:00',
        True,
        'Thursday 2017-01-05 16:00',
        'Friday 2017-01-06 16:00',
    ),
    #  Monday at 17:00 GMT
    (
        'Monday 2017-01-02 17:00:01',
        'Wednesday 2017-01-04 15:00',
        True,
        'Friday 2017-01-06 16:00',
        'Saturday 2017-01-07 16:00',
    ),

])
def test_get_estimated_delivery_date_for_letter(
    upload_time,
    expected_print_time,
    is_printed,
    expected_earliest,
    expected_latest,
):
    # remove the day string from the upload_time, which is purely informational

    format_dt = lambda x: x.astimezone(pytz.timezone('Europe/London')).strftime('%A %Y-%m-%d %H:%M')  # noqa

    upload_time = upload_time.split(' ', 1)[1]

    timings = get_letter_timings(upload_time)

    assert format_dt(timings.printed_by) == expected_print_time
    assert timings.is_printed == is_printed
    assert format_dt(timings.earliest_delivery) == expected_earliest
    assert format_dt(timings.latest_delivery) == expected_latest
