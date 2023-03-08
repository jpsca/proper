import hashlib
import json

from itsdangerous import (
    BadSignature,
    Signer as iSigner,
    URLSafeTimedSerializer,
)


__all__ = ("BadSignature", "Serializer", "Signer")


def decode(value: str | bytes) -> str:
    if isinstance(value, bytes):
        return value.decode("utf8")
    return value


class Signer(iSigner):
    def __init__(
        self,
        secret_keys: str | list[str],
        namespace: str = "proper",
        **kwargs,
    ) -> None:
        kwargs["salt"] = namespace
        kwargs.setdefault("key_derivation", "hmac")
        kwargs.setdefault("digest_method", hashlib.sha1)
        super().__init__(secret_keys, **kwargs)

    def sign(self, value: str | bytes) -> str:
        return decode(super().sign(value))

    def unsign(self, signed_value: str | bytes) -> str:
        return decode(super().unsign(signed_value))


class Serializer(URLSafeTimedSerializer):
    def __init__(
        self,
        secret_keys: str | list[str],
        namespace: str = "proper",
        **kwargs,
    ) -> None:
        kwargs["salt"] = namespace
        kwargs.setdefault("serializer", json)
        kwargs.setdefault(
            "signer_kwargs",
            {
                "key_derivation": "hmac",
                "digest_method": hashlib.sha1,
            },
        )
        super().__init__(secret_keys, **kwargs)

    def dumps(self, dict_value: dict) -> str:
        return decode(super().dumps(dict_value))
