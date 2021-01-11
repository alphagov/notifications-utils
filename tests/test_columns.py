from functools import partial

import pytest

from notifications_utils.columns import Cell, Columns, Row


def test_columns_as_dict_with_keys():
    assert Columns({
        'Date of Birth': '01/01/2001',
        'TOWN': 'London'
    }).as_dict_with_keys({'date_of_birth', 'town'}) == {
        'date_of_birth': '01/01/2001',
        'town': 'London'
    }


def test_columns_as_dict():
    assert dict(Columns({
        'date of birth': '01/01/2001',
        'TOWN': 'London'
    })) == {
        'dateofbirth': '01/01/2001',
        'town': 'London'
    }


def test_missing_data():
    partial_row = partial(
        Row,
        row_dict={},
        index=1,
        error_fn=None,
        recipient_column_headers=[],
        placeholders=[],
        template=None,
        allow_international_letters=False,
    )
    with pytest.raises(KeyError):
        Columns({})['foo']
    assert Columns({}).get('foo') is None
    assert Columns({}).get('foo', 'bar') == 'bar'
    assert partial_row()['foo'] == Cell()
    assert partial_row().get('foo') == Cell()
    assert partial_row().get('foo', 'bar') == 'bar'


@pytest.mark.parametrize('in_dictionary', [
    {'foo': 'bar'},
    {'F_O O': 'bar'},
])
@pytest.mark.parametrize('key, should_be_present', [
    ('foo', True),
    ('f_o_o', True),
    ('F O O', True),
    ('bar', False),
])
def test_lookup(key, should_be_present, in_dictionary):
    assert (key in Columns(in_dictionary)) == should_be_present


@pytest.mark.parametrize('key_in', [
    'foo',
    'F_O O',
])
@pytest.mark.parametrize('lookup_key', [
    'foo',
    'f_o_o',
    'F O O',
])
def test_set_item(key_in, lookup_key):
    columns = Columns({})
    columns[key_in] = 'bar'
    assert columns[lookup_key] == 'bar'
