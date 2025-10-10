from datetime import UTC, datetime

import pytest
from freezegun import freeze_time

from notifications_utils.letter_timings import (
    get_dvla_working_day_offset_by,
    get_letter_timings,
    get_next_dvla_working_day,
    get_next_royal_mail_working_day,
    get_previous_dvla_working_day,
    get_previous_royal_mail_working_day,
    get_royal_mail_working_day_offset_by,
    is_dvla_working_day,
    is_royal_mail_working_day_default,
    is_royal_mail_working_day_first_class,
    letter_can_be_cancelled,
)
from notifications_utils.timezones import local_timezone


@freeze_time("2017-07-14 13:59:59")  # Friday, before print deadline (3PM BST)
@pytest.mark.parametrize(
    (
        "upload_time, "
        "expected_print_time, "
        "is_printed, "
        "first_class, "
        "expected_earliest_second_class, "
        "expected_latest_second_class, "
        "expected_earliest_economy, "
        "expected_latest_economy, "
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
            "Tuesday 2017-07-18 16:00",
            "Monday 2017-07-17 16:00",
            "Thursday 2017-07-20 16:00",
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
            "Tuesday 2017-07-18 16:00",
            "Monday 2017-07-17 16:00",
            "Thursday 2017-07-20 16:00",
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
            "Wednesday 2017-07-19 16:00",
            "Tuesday 2017-07-18 16:00",
            "Friday 2017-07-21 16:00",
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
            "Wednesday 2017-07-19 16:00",
            "Tuesday 2017-07-18 16:00",
            "Friday 2017-07-21 16:00",
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
            "Thursday 2017-07-20 16:00",
            "Wednesday 2017-07-19 16:00",
            "Monday 2017-07-24 16:00",
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
            "Friday 2017-07-21 16:00",
            "Thursday 2017-07-20 16:00",
            "Tuesday 2017-07-25 16:00",
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
            "Monday 2017-07-24 16:00",
            "Friday 2017-07-21 16:00",
            "Wednesday 2017-07-26 16:00",
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
            "Monday 2017-07-24 16:00",
            "Friday 2017-07-21 16:00",
            "Wednesday 2017-07-26 16:00",
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
            "Monday 2017-07-24 16:00",
            "Friday 2017-07-21 16:00",
            "Wednesday 2017-07-26 16:00",
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
            "Monday 2017-07-24 16:00",
            "Friday 2017-07-21 16:00",
            "Wednesday 2017-07-26 16:00",
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
            "Monday 2017-07-24 16:00",
            "Friday 2017-07-21 16:00",
            "Wednesday 2017-07-26 16:00",
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
            "Tuesday 2017-07-25 16:00",
            "Monday 2017-07-24 16:00",
            "Thursday 2017-07-27 16:00",
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
            "Tuesday 2017-01-10 16:00",
            "Monday 2017-01-09 16:00",
            "Thursday 2017-01-12 16:00",
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
            "Wednesday 2017-01-11 16:00",
            "Tuesday 2017-01-10 16:00",
            "Friday 2017-01-13 16:00",
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
            "Tuesday 2020-04-21 16:00",
            "Monday 2020-04-20 16:00",
            "Thursday 2020-04-23 16:00",
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
    expected_earliest_second_class,
    expected_latest_second_class,
    expected_earliest_economy,
    expected_latest_economy,
    expected_earliest_europe,
    expected_latest_europe,
    expected_earliest_rest_of_world,
    expected_latest_rest_of_world,
):
    # remove the day string from the upload_time, which is purely informational

    format_dt = lambda x: x.astimezone(local_timezone).strftime("%A %Y-%m-%d %H:%M")  # noqa

    upload_time = upload_time.split(" ", 1)[1]

    second_class_timings = get_letter_timings(upload_time, postage="second")

    assert format_dt(second_class_timings.printed_by) == expected_print_time
    assert second_class_timings.is_printed == is_printed
    assert format_dt(second_class_timings.earliest_delivery) == expected_earliest_second_class
    assert format_dt(second_class_timings.latest_delivery) == expected_latest_second_class

    economy_timings = get_letter_timings(upload_time, postage="economy")

    assert format_dt(economy_timings.printed_by) == expected_print_time
    assert economy_timings.is_printed == is_printed
    assert format_dt(economy_timings.earliest_delivery) == expected_earliest_economy
    assert format_dt(economy_timings.latest_delivery) == expected_latest_economy

    first_class_timings = get_letter_timings(upload_time, postage="first")

    assert format_dt(first_class_timings.printed_by) == expected_print_time
    assert first_class_timings.is_printed == is_printed
    assert format_dt(first_class_timings.earliest_delivery) == first_class
    assert format_dt(first_class_timings.latest_delivery) == first_class

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


def test_letter_timings_only_accept_real_postage_values():
    with pytest.raises(KeyError):
        get_letter_timings(datetime.now(UTC).isoformat(), postage="foo")


@pytest.mark.parametrize("status", ["sending", "pending"])
def test_letter_cannot_be_cancelled_if_letter_status_is_not_created_or_pending_virus_check(status):
    notification_created_at = datetime.now(UTC)

    assert not letter_can_be_cancelled(status, notification_created_at)


@freeze_time("2018-7-7 16:00:00")
@pytest.mark.parametrize(
    "notification_created_at",
    [
        datetime(2018, 7, 6, 18, 0),  # created yesterday after 1730
        datetime(2018, 7, 7, 12, 0),  # created today
    ],
)
def test_letter_can_be_cancelled_if_before_1730_and_letter_created_before_1730(notification_created_at):
    notification_status = "pending-virus-check"

    assert letter_can_be_cancelled(notification_status, notification_created_at)


@freeze_time("2017-12-12 17:30:00")
@pytest.mark.parametrize(
    "notification_created_at",
    [
        datetime(2017, 12, 12, 17, 0),
        datetime(2017, 12, 12, 17, 30),
    ],
)
def test_letter_cannot_be_cancelled_if_1730_exactly_and_letter_created_at_or_before_1730(notification_created_at):
    notification_status = "pending-virus-check"

    assert not letter_can_be_cancelled(notification_status, notification_created_at)


@freeze_time("2018-7-7 19:00:00")
@pytest.mark.parametrize(
    "notification_created_at",
    [
        datetime(2018, 7, 6, 18, 0),  # created yesterday after 1730
        datetime(2018, 7, 7, 12, 0),  # created today before 1730
    ],
)
def test_letter_cannot_be_cancelled_if_after_1730_and_letter_created_before_1730(notification_created_at):
    notification_status = "created"

    assert not letter_can_be_cancelled(notification_status, notification_created_at)


@freeze_time("2018-7-7 15:00:00")
def test_letter_cannot_be_cancelled_if_before_1730_and_letter_created_before_1730_yesterday():
    notification_status = "created"

    assert not letter_can_be_cancelled(notification_status, datetime(2018, 7, 6, 14, 0))


@freeze_time("2018-7-7 15:00:00")
def test_letter_cannot_be_cancelled_if_before_1730_and_letter_created_after_1730_two_days_ago():
    notification_status = "created"

    assert not letter_can_be_cancelled(notification_status, datetime(2018, 7, 5, 19, 0))


@freeze_time("2018-7-7 19:00:00")
@pytest.mark.parametrize(
    "notification_created_at",
    [
        datetime(2018, 7, 7, 17, 30),
        datetime(2018, 7, 7, 18, 0),
    ],
)
def test_letter_can_be_cancelled_if_after_1730_and_letter_created_at_1730_today_or_later(notification_created_at):
    notification_status = "created"

    assert letter_can_be_cancelled(notification_status, notification_created_at)


@freeze_time("2018-7-7 10:00:00")
@pytest.mark.parametrize(
    "notification_created_at",
    [
        datetime(2018, 7, 6, 20, 30),  # yesterday after deadline
        datetime(2018, 7, 6, 23, 30),  # this morning after deadline but yesterday in UTC
        datetime(2018, 7, 7, 3, 30),  # this morning after deadline, and today in UTC
    ],
)
def test_letter_can_be_cancelled_always_compares_in_bst(notification_created_at):
    assert letter_can_be_cancelled("created", notification_created_at)


def test_next_previous_working_days():
    friday_23_december = datetime(2022, 12, 23, 12, 0, 0)
    saturday_24_december = datetime(2022, 12, 24, 12, 0, 0)
    sunday_25_december = datetime(2022, 12, 25, 12, 0, 0)
    monday_26_december = datetime(2022, 12, 26, 12, 0, 0)
    tuesday_27_december = datetime(2022, 12, 27, 12, 0, 0)
    wednesday_28_december = datetime(2022, 12, 28, 12, 0, 0)

    # DVLA and Royal Mail don’t work on Sundays or bank holidays
    assert not is_dvla_working_day(sunday_25_december)
    assert not is_dvla_working_day(monday_26_december)
    assert not is_dvla_working_day(tuesday_27_december)
    assert get_next_dvla_working_day(monday_26_december) == wednesday_28_december

    assert not is_royal_mail_working_day_default(sunday_25_december)
    assert not is_royal_mail_working_day_default(monday_26_december)
    assert not is_royal_mail_working_day_default(tuesday_27_december)
    assert get_next_royal_mail_working_day(monday_26_december, "second") == wednesday_28_december

    # DVLA don’t work Saturdays
    assert not is_dvla_working_day(saturday_24_december)
    assert get_previous_dvla_working_day(monday_26_december) == friday_23_december

    # Royal Mail don't work Saturdays for non-first class mail
    assert not is_royal_mail_working_day_default(saturday_24_december)
    assert get_previous_royal_mail_working_day(monday_26_december, "second") == friday_23_december


def test_next_previous_working_days_royal_mail_first_class():
    saturday_24_december = datetime(2022, 12, 24, 12, 0, 0)
    sunday_25_december = datetime(2022, 12, 25, 12, 0, 0)
    monday_26_december = datetime(2022, 12, 26, 12, 0, 0)
    tuesday_27_december = datetime(2022, 12, 27, 12, 0, 0)
    wednesday_28_december = datetime(2022, 12, 28, 12, 0, 0)

    assert not is_royal_mail_working_day_first_class(sunday_25_december)
    assert not is_royal_mail_working_day_first_class(monday_26_december)
    assert not is_royal_mail_working_day_first_class(tuesday_27_december)
    assert get_next_royal_mail_working_day(monday_26_december, "first") == wednesday_28_december

    # Royal Mail do work Saturdays for first class mail
    assert is_royal_mail_working_day_first_class(saturday_24_december)
    assert get_previous_royal_mail_working_day(monday_26_december, "first") == saturday_24_december


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
    assert get_royal_mail_working_day_offset_by(friday_23_december, days=-5, postage="first") == saturday_17_december
    # 5 days backward, skipping weekend for non-first class mail
    assert get_royal_mail_working_day_offset_by(friday_23_december, days=-5, postage="economy") == friday_16_december


def test_get_0_offset_working_days_dvla():
    with pytest.raises(ValueError) as error:
        get_dvla_working_day_offset_by(datetime.now(), days=0)
    assert str(error.value) == "days argument must not be 0"


def test_get_0_offset_working_days_royal_mail():
    with pytest.raises(ValueError) as error:
        get_royal_mail_working_day_offset_by(datetime.now(), days=0, postage="second")
    assert str(error.value) == "days argument must not be 0"
