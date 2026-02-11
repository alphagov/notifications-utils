import pytest

from notifications_utils.exception_handling import extract_reraise_chained_exception


class ExampleException(Exception):
    pass


def test_extract_reraise_chained_direct():
    with pytest.raises(ExampleException):
        with extract_reraise_chained_exception(ExampleException):
            raise ExampleException


def test_extract_reraise_chained_direct_unrelated():
    with pytest.raises(ZeroDivisionError):
        with extract_reraise_chained_exception(ExampleException):
            return 1 / 0


def test_extract_reraise_chained_explicit():
    with pytest.raises(ExampleException):
        with extract_reraise_chained_exception(ExampleException):
            try:
                raise ExampleException
            except Exception as e:
                raise ValueError("oh dear") from e


def test_extract_reraise_chained_implicit():
    with pytest.raises(ExampleException):
        with extract_reraise_chained_exception(ExampleException):
            try:
                raise ExampleException
            except Exception:
                return 1 / 0


def test_extract_reraise_chained_explicit_nullified():
    with pytest.raises(ExampleException):
        with extract_reraise_chained_exception(ExampleException):
            try:
                raise ExampleException
            except Exception:
                raise ValueError("oh dear") from None


def test_extract_reraise_chained_explicit_multiple():
    with pytest.raises(ExampleException):
        with extract_reraise_chained_exception((KeyError, ExampleException)):
            try:
                raise ExampleException
            except Exception as e:
                raise ValueError("oh dear") from e


def test_extract_reraise_chained_deep_0():
    with pytest.raises(ExampleException):
        with extract_reraise_chained_exception(ExampleException):
            try:
                try:
                    try:
                        raise ExampleException
                    except ExampleException as e:
                        raise ValueError("oh dear") from e
                except ValueError:
                    try:
                        return 1 / 0
                    except ZeroDivisionError:
                        raise RuntimeError("crikey") from None
            except Exception:
                raise TypeError("oh my") from None


def test_extract_reraise_chained_deep_1():
    with pytest.raises(ExampleException):
        with extract_reraise_chained_exception(ExampleException):
            try:
                try:
                    try:
                        raise RuntimeError("crikey")
                    except RuntimeError as e:
                        raise ValueError("oh dear") from e
                except ValueError:
                    try:
                        return 1 / 0
                    except ZeroDivisionError:
                        raise ExampleException from None
            except Exception:
                raise TypeError("oh my") from None


def test_extract_reraise_chained_deep_unrelated():
    with pytest.raises(TypeError):
        with extract_reraise_chained_exception(ExampleException):
            try:
                try:
                    try:
                        raise RuntimeError("crikey")
                    except RuntimeError as e:
                        raise ValueError("oh dear") from e
                except ValueError:
                    try:
                        return 1 / 0
                    except ZeroDivisionError:
                        raise SystemError from None
            except Exception:
                raise TypeError("oh my") from None
