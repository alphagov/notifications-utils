from uuid import UUID
import os

import pytest
from werkzeug.routing import ValidationError

from notifications_utils.base64_uuid import Base64UUIDConverter, base64_to_bytes, bytes_to_base64


def test_bytes_to_base64_to_bytes():
    b = os.urandom(32)
    b64 = bytes_to_base64(b)
    assert base64_to_bytes(b64) == b


@pytest.mark.parametrize('url_val', [
    'AAAAAAAAAAAAAAAAAAAAAQ',
    'AAAAAAAAAAAAAAAAAAAAAQ=',  # even though this has invalid padding we put extra =s on the end so this is okay
    'AAAAAAAAAAAAAAAAAAAAAQ==',
])
def test_base64_converter_to_python(url_val):
    assert Base64UUIDConverter(None).to_python(url_val) == UUID(int=1)


@pytest.mark.parametrize('python_val', [
    UUID(int=1),
    '00000000-0000-0000-0000-000000000001'
])
def test_base64_converter_to_url(python_val):
    assert Base64UUIDConverter(None).to_url(python_val) == 'AAAAAAAAAAAAAAAAAAAAAQ'


@pytest.mark.parametrize('url_val', [
    'this_is_valid_base64_but_is_too_long_to_be_a_uuid',
    'this_one_has_emoji_➕➕➕',
])
def test_base64_converter_to_python_raises_validation_error(url_val):
    with pytest.raises(ValidationError):
        Base64UUIDConverter(None).to_python(url_val)


def test_base64_converter_to_url_raises_validation_error():
    with pytest.raises(ValidationError):
        Base64UUIDConverter(None).to_url(object())
