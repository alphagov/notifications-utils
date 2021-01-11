from datetime import datetime

import pytest

from notifications_utils.timezones import (
    convert_bst_to_utc,
    convert_utc_to_bst,
    utc_string_to_aware_gmt_datetime,
)


@pytest.mark.parametrize('input_value', [
    'foo',
    100,
    True,
    False,
    None,
])
def test_utc_string_to_aware_gmt_datetime_rejects_bad_input(input_value):
    with pytest.raises(Exception):
        utc_string_to_aware_gmt_datetime(input_value)


def test_utc_string_to_aware_gmt_datetime_accepts_datetime_objects():
    input_value = datetime(2017, 5, 12, 14, 0)
    expected = '2017-05-12T15:00:00+01:00'
    assert utc_string_to_aware_gmt_datetime(input_value).isoformat() == expected


@pytest.mark.parametrize('naive_time, expected_aware_hour', [
    ('2000-12-1 20:01', '20:01'),
    ('2000-06-1 20:01', '21:01'),
    ('2000-06-1T20:01+00:00', '21:01'),
])
def test_utc_string_to_aware_gmt_datetime_handles_summer_and_winter(
    naive_time,
    expected_aware_hour,
):
    assert utc_string_to_aware_gmt_datetime(naive_time).strftime('%H:%M') == expected_aware_hour


@pytest.mark.parametrize('date, expected_date', [
    (datetime(2017, 3, 26, 23, 0), datetime(2017, 3, 27, 0, 0)),    # 2017 BST switchover
    (datetime(2017, 3, 20, 23, 0), datetime(2017, 3, 20, 23, 0)),
    (datetime(2017, 3, 28, 10, 0), datetime(2017, 3, 28, 11, 0)),
    (datetime(2017, 10, 28, 1, 0), datetime(2017, 10, 28, 2, 0)),
    (datetime(2017, 10, 29, 1, 0), datetime(2017, 10, 29, 1, 0)),
    (datetime(2017, 5, 12, 14), datetime(2017, 5, 12, 15, 0))
])
def test_get_utc_in_bst_returns_expected_date(date, expected_date):
    ret_date = convert_utc_to_bst(date)
    assert ret_date == expected_date


def test_convert_bst_to_utc():
    bst = "2017-05-12 13:15"
    bst_datetime = datetime.strptime(bst, "%Y-%m-%d %H:%M")
    utc = convert_bst_to_utc(bst_datetime)
    assert utc == datetime(2017, 5, 12, 12, 15)
