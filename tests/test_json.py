import datetime
import json

import pytest
from requests.structures import CaseInsensitiveDict

from notifications_utils.insensitive_dict import InsensitiveDict, InsensitiveSet
from notifications_utils.json import RelaxedContainerJSONEncoder


@pytest.mark.parametrize(
    "input_value, expected_output",
    (
        (None, None),
        (123, 123),
        (True, True),
        (False, False),
        ({"foo": 123}, {"foo": 123}),
        ([123, "foo", None], [123, "foo", None]),
        (
            [([],)],
            [[[]]],
        ),
        (CaseInsensitiveDict({"foo": 123}), {"foo": 123}),
        (InsensitiveDict({"foo": 123}), {"foo": 123}),
        (InsensitiveSet(("foo", "bar", "Baz")), ["foo", "bar", "Baz"]),
        (InsensitiveSet(("foo", None, "Baz")), ["foo", None, "Baz"]),
        (
            [InsensitiveDict({"foo": (InsensitiveDict({"foo": 123}), "baa")}), InsensitiveSet(("2", "1")), None],
            [{"foo": [{"foo": 123}, "baa"]}, ["2", "1"], None],
        ),
    ),
)
def test_relaxed_container_json_encoder(input_value, expected_output):
    json_encoded = RelaxedContainerJSONEncoder().encode(input_value)
    assert json.loads(json_encoded) == expected_output


@pytest.mark.parametrize(
    "input_value",
    ({1, 2, 3}, datetime.datetime.fromisoformat("2020-10-10T01:02:03"), b"foo"),
)
def test_relaxed_container_json_encoder_unencodable(input_value):
    with pytest.raises(TypeError):
        RelaxedContainerJSONEncoder().encode(input_value)

    with pytest.raises(TypeError):
        RelaxedContainerJSONEncoder().encode([input_value])

    with pytest.raises(TypeError):
        RelaxedContainerJSONEncoder().encode({"foo": input_value})
