from uuid import UUID
from base64 import urlsafe_b64encode, urlsafe_b64decode

from werkzeug.routing import BaseConverter, ValidationError


def base64_to_bytes(key):
    return urlsafe_b64decode(key + '==')


def bytes_to_base64(bytes):
    # remove trailing = to save precious bytes
    return urlsafe_b64encode(bytes).decode('ascii').rstrip('=')


class Base64UUIDConverter(BaseConverter):
    def to_python(self, value):
        try:
            # uuids are 16 bytes, and will always have two ==s of padding
            return UUID(bytes=urlsafe_b64decode(value.encode('ascii') + b'=='))
        except ValueError:
            raise ValidationError()

    def to_url(self, value):
        try:
            if not isinstance(value, UUID):
                value = UUID(value)
            return bytes_to_base64(value.bytes)
        except (AttributeError, ValueError):
            raise ValidationError()
