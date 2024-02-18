from collections.abc import Generator
from contextlib import contextmanager, AbstractContextManager
import hmac
import json
from typing import Optional, NewType, Union

from cryptography.fernet import Fernet, MultiFernet

from flask import current_app


FernetOrMulti = Union[Fernet, MultiFernet]
# based on https://github.com/python/typing/issues/182#issuecomment-1320974824 with an
# attempt to make dangerous strings more trackable
TaintedStr = NewType("TaintedStr", str)
TaintedJSONable = Union[
    dict[TaintedStr, "TaintedJSONable"],
    list["TaintedJSONable"],
    TaintedStr,
    int,
    float,
    bool,
    None,
]


class NotifySealedValue:
    _sealed_data: bytes

    def __init__(
        self,
        value: TaintedJSONable=None,
        fernet: Optional[FernetOrMulti]=None,
        *,
        load_sealed: Optional[bytes]=None,
    ):
        if fernet is not None:
            if load_sealed is not None:
                raise TypeError("Cannot specify both fernet and load_sealed arguments")
            object.__setattr__(
                self,
                "_sealed_data",
                fernet.encrypt(json.dumps(value, separators=(',', ':')).encode("utf8")),
            )
            return

        if load_sealed is not None:
            object.__setattr__(self, "_sealed_data", load_sealed)
            return

        raise TypeError("Must specify either fernet or load_sealed argument")

    @contextmanager
    def unsealed(self, fernet: FernetOrMulti) -> Generator[TaintedJSONable, None, None]:
        yield json.loads(fernet.decrypt(self._sealed_data).decode("utf8"))

    def dump_sealed(self) -> bytes:
        return self._sealed_data

    def __str__(self):
        return f"{type(self).__name__}(<{len(self._sealed_data)}B sealed data>)"

    def __repr__(self):
        return str(self)

    def __setattr__(self, *_):
        raise TypeError(f"{type(self).__name__} is intended to be treated as immutable")


class FlaskNotifySealedValue(NotifySealedValue):
    def __init__(
        self,
        value: TaintedJSONable=None,
        *,
        load_sealed: Optional[bytes]=None,
    ):
        if load_sealed is not None:
            if value is not None:
                raise TypeError("Cannot specify both value and load_sealed arguments")

            super().__init__(load_sealed=load_sealed)

        super().__init__(value, self._get_fernet())

    def unsealed(self, fernet: Optional[FernetOrMulti]=None) -> AbstractContextManager[TaintedJSONable]:
        if fernet is None:
            fernet = self._get_fernet()
        return super().unsealed(fernet)

    @classmethod
    def _get_fernet(cls) -> FernetOrMulti:
        base_key = (
            current_app.config.get("NOTIFY_SEALED_VALUE_SECRET_KEY")
            or current_app.config["SECRET_KEY"]
        )
        return Fernet(hmac.digest(b"NotifySealedValue", base_key, "sha256"))
