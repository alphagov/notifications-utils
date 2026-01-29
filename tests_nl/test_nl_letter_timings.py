from datetime import datetime

import pytest
import pytz
from freezegun import freeze_time

from notifications_utils.letter_timings import (
    get_dvla_working_day_offset_by,
    get_letter_timings,
    get_next_royal_mail_working_day,
    get_previous_royal_mail_working_day,
    get_royal_mail_working_day_offset_by,
    is_royal_mail_working_day_first_class,
)


@freeze_time("2017-07-14 13:59:59")  # Friday, before print deadline (3PM BST)
@pytest.mark.parametrize(
    (
        "upload_time, "
        "expected_print_time, "
        "is_printed, "
        "first_class, "
        "expected_earliest_europe, "
        "expected_latest_europe, "
        "expected_earliest_rest_of_world, "
        "expected_latest_rest_of_world, "
    ),
    [
        # BST
        # ==================================================================
        #  First thing Monday
        (
            "Monday 2017-07-10 00:00:01",
            "Tuesday 2017-07-11 15:00",
            True,
            "Wednesday 2017-07-12 16:00",
            "Monday 2017-07-17 16:00",
            "Wednesday 2017-07-19 16:00",
            "Wednesday 2017-07-19 16:00",
            "Friday 2017-07-21 16:00",
        ),
        #  Monday at 17:29 BST (sent on monday)
        (
            "Monday 2017-07-10 16:29:59",
            "Tuesday 2017-07-11 15:00",
            True,
            "Wednesday 2017-07-12 16:00",
            "Monday 2017-07-17 16:00",
            "Wednesday 2017-07-19 16:00",
            "Wednesday 2017-07-19 16:00",
            "Friday 2017-07-21 16:00",
        ),
        #  Monday at 17:30 BST (sent on tuesday)
        (
            "Monday 2017-07-10 16:30:01",
            "Wednesday 2017-07-12 15:00",
            True,
            "Thursday 2017-07-13 16:00",
            "Tuesday 2017-07-18 16:00",
            "Thursday 2017-07-20 16:00",
            "Thursday 2017-07-20 16:00",
            "Monday 2017-07-24 16:00",
        ),
        #  Tuesday before 17:30 BST
        (
            "Tuesday 2017-07-11 12:00:00",
            "Wednesday 2017-07-12 15:00",
            True,
            "Thursday 2017-07-13 16:00",
            "Tuesday 2017-07-18 16:00",
            "Thursday 2017-07-20 16:00",
            "Thursday 2017-07-20 16:00",
            "Monday 2017-07-24 16:00",
        ),
        #  Wednesday before 17:30 BST
        (
            "Wednesday 2017-07-12 12:00:00",
            "Thursday 2017-07-13 15:00",
            True,
            "Friday 2017-07-14 16:00",
            "Wednesday 2017-07-19 16:00",
            "Friday 2017-07-21 16:00",
            "Friday 2017-07-21 16:00",
            "Tuesday 2017-07-25 16:00",
        ),
        #  Thursday before 17:30 BST
        (
            "Thursday 2017-07-13 12:00:00",
            "Friday 2017-07-14 15:00",
            False,
            "Saturday 2017-07-15 16:00",
            "Thursday 2017-07-20 16:00",
            "Monday 2017-07-24 16:00",
            "Monday 2017-07-24 16:00",
            "Wednesday 2017-07-26 16:00",
        ),
        #  Friday anytime
        (
            "Friday 2017-07-14 00:00:00",
            "Monday 2017-07-17 15:00",
            False,
            "Tuesday 2017-07-18 16:00",
            "Friday 2017-07-21 16:00",
            "Tuesday 2017-07-25 16:00",
            "Tuesday 2017-07-25 16:00",
            "Thursday 2017-07-27 16:00",
        ),
        (
            "Friday 2017-07-14 12:00:00",
            "Monday 2017-07-17 15:00",
            False,
            "Tuesday 2017-07-18 16:00",
            "Friday 2017-07-21 16:00",
            "Tuesday 2017-07-25 16:00",
            "Tuesday 2017-07-25 16:00",
            "Thursday 2017-07-27 16:00",
        ),
        (
            "Friday 2017-07-14 22:00:00",
            "Monday 2017-07-17 15:00",
            False,
            "Tuesday 2017-07-18 16:00",
            "Friday 2017-07-21 16:00",
            "Tuesday 2017-07-25 16:00",
            "Tuesday 2017-07-25 16:00",
            "Thursday 2017-07-27 16:00",
        ),
        #  Saturday anytime
        (
            "Saturday 2017-07-14 12:00:00",
            "Monday 2017-07-17 15:00",
            False,
            "Tuesday 2017-07-18 16:00",
            "Friday 2017-07-21 16:00",
            "Tuesday 2017-07-25 16:00",
            "Tuesday 2017-07-25 16:00",
            "Thursday 2017-07-27 16:00",
        ),
        #  Sunday before 1730 BST
        (
            "Sunday 2017-07-15 15:59:59",
            "Monday 2017-07-17 15:00",
            False,
            "Tuesday 2017-07-18 16:00",
            "Friday 2017-07-21 16:00",
            "Tuesday 2017-07-25 16:00",
            "Tuesday 2017-07-25 16:00",
            "Thursday 2017-07-27 16:00",
        ),
        #  Sunday after 17:30 BST
        (
            "Sunday 2017-07-16 16:30:01",
            "Tuesday 2017-07-18 15:00",
            False,
            "Wednesday 2017-07-19 16:00",
            "Monday 2017-07-24 16:00",
            "Wednesday 2017-07-26 16:00",
            "Wednesday 2017-07-26 16:00",
            "Friday 2017-07-28 16:00",
        ),
        # GMT
        # ==================================================================
        #  Monday at 17:29 GMT
        (
            "Monday 2017-01-02 17:29:59",
            "Tuesday 2017-01-03 15:00",
            True,
            "Wednesday 2017-01-04 16:00",
            "Monday 2017-01-09 16:00",
            "Wednesday 2017-01-11 16:00",
            "Wednesday 2017-01-11 16:00",
            "Friday 2017-01-13 16:00",
        ),
        #  Monday at 17:00 GMT
        (
            "Monday 2017-01-02 17:30:01",
            "Wednesday 2017-01-04 15:00",
            True,
            "Thursday 2017-01-05 16:00",
            "Tuesday 2017-01-10 16:00",
            "Thursday 2017-01-12 16:00",
            "Thursday 2017-01-12 16:00",
            "Monday 2017-01-16 16:00",
        ),
        # Over Easter bank holiday weekend
        (
            "Thursday 2020-04-09 16:29:59",
            "Tuesday 2020-04-14 15:00",
            False,
            "Wednesday 2020-04-15 16:00",
            "Monday 2020-04-20 16:00",
            "Wednesday 2020-04-22 16:00",
            "Wednesday 2020-04-22 16:00",
            "Friday 2020-04-24 16:00",
        ),
    ],
)
def test_get_estimated_delivery_date_for_letter(
    upload_time,
    expected_print_time,
    is_printed,
    first_class,
    expected_earliest_europe,
    expected_latest_europe,
    expected_earliest_rest_of_world,
    expected_latest_rest_of_world,
):
    # remove the day string from the upload_time, which is purely informational

    format_dt = lambda x: x.astimezone(pytz.timezone("Europe/London")).strftime("%A %Y-%m-%d %H:%M")  # noqa

    upload_time = upload_time.split(" ", 1)[1]

    nl_timings = get_letter_timings(upload_time, postage="netherlands")

    assert format_dt(nl_timings.printed_by) == expected_print_time
    assert nl_timings.is_printed == is_printed
    assert format_dt(nl_timings.earliest_delivery) == first_class
    assert format_dt(nl_timings.latest_delivery) == first_class

    europe_timings = get_letter_timings(upload_time, postage="europe")

    assert format_dt(europe_timings.printed_by) == expected_print_time
    assert europe_timings.is_printed == is_printed
    assert format_dt(europe_timings.earliest_delivery) == expected_earliest_europe
    assert format_dt(europe_timings.latest_delivery) == expected_latest_europe

    rest_of_world_timings = get_letter_timings(upload_time, postage="rest-of-world")

    assert format_dt(rest_of_world_timings.printed_by) == expected_print_time
    assert rest_of_world_timings.is_printed == is_printed
    assert format_dt(rest_of_world_timings.earliest_delivery) == expected_earliest_rest_of_world
    assert format_dt(rest_of_world_timings.latest_delivery) == expected_latest_rest_of_world


def test_next_previous_working_days_royal_mail_first_class():
    saturday_24_december = datetime(2022, 12, 24, 12, 0, 0)
    sunday_25_december = datetime(2022, 12, 25, 12, 0, 0)
    monday_26_december = datetime(2022, 12, 26, 12, 0, 0)
    tuesday_27_december = datetime(2022, 12, 27, 12, 0, 0)
    wednesday_28_december = datetime(2022, 12, 28, 12, 0, 0)

    assert not is_royal_mail_working_day_first_class(sunday_25_december)
    assert not is_royal_mail_working_day_first_class(monday_26_december)
    assert not is_royal_mail_working_day_first_class(tuesday_27_december)
    assert get_next_royal_mail_working_day(monday_26_december, "netherlands") == wednesday_28_december

    # Royal Mail do work Saturdays for first class mail
    assert is_royal_mail_working_day_first_class(saturday_24_december)
    assert get_previous_royal_mail_working_day(monday_26_december, "netherlands") == saturday_24_december


def test_get_offset_working_day():
    friday_16_december = datetime(2022, 12, 16, 12, 0, 0)
    saturday_17_december = datetime(2022, 12, 17, 12, 0, 0)
    thursday_22_december = datetime(2022, 12, 22, 12, 0, 0)
    friday_23_december = datetime(2022, 12, 23, 12, 0, 0)
    wednesday_28_december = datetime(2022, 12, 28, 12, 0, 0)
    thursday_29_december = datetime(2022, 12, 29, 12, 0, 0)

    # 1 day forward, skipping weekend and bank holidays
    assert get_dvla_working_day_offset_by(friday_23_december, days=1) == wednesday_28_december
    # 2 day forward, skipping weekend, bank holidays, and 1 working day
    assert get_dvla_working_day_offset_by(friday_23_december, days=2) == thursday_29_december

    # 1 day backward, skipping no days
    assert get_dvla_working_day_offset_by(friday_23_december, days=-1) == thursday_22_december
    # 5 days backward, skipping weekend
    assert get_dvla_working_day_offset_by(friday_23_december, days=-5) == friday_16_december
    # 5 days backward, skipping Saturday only for first class mail
    assert (
        get_royal_mail_working_day_offset_by(friday_23_december, days=-5, postage="netherlands") == saturday_17_december
    )
    # 5 days backward, skipping weekend for non-first class mail
