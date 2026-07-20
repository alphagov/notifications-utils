import json

import pytest
from requests.structures import CaseInsensitiveDict

from notifications_utils.insensitive_dict import InsensitiveDict, InsensitiveSet
from notifications_utils.json import json_encodable


@pytest.mark.parametrize(
    "input_value, expected_output",
    (
        (None, None),
        (123, 123),
        (True, True),
        (False, False),
        ({"foo": 123}, {"foo": 123}),
        ([123, "foo", None], (123, "foo", None)),
        (
            [([],)],
            (((),),),
        ),
        (CaseInsensitiveDict({"foo": 123}), {"foo": 123}),
        (InsensitiveDict({"foo": 123}), {"foo": 123}),
        (InsensitiveSet(("foo", "bar", "Baz")), ("foo", "bar", "Baz")),
        (InsensitiveSet(("foo", None, "Baz")), ("foo", None, "Baz")),
        (
            [InsensitiveDict({"foo": (InsensitiveDict({"foo": 123}), "baa")}), InsensitiveSet(("2", "1")), None],
            ({"foo": ({"foo": 123}, "baa")}, ("2", "1"), None),
        ),
    ),
)
def test_json_encodable(input_value, expected_output):
    result = json_encodable(input_value)
    assert result == expected_output

    json.dumps(json_encodable(input_value))
