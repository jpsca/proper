"""A wrapper arround the `URLSafeTimedSerializer` from "ItsDangerous".

Used by proper to serialize the session and available to the user for other things.
"""
import hashlib
import json

from itsdangerous import BadSignature, URLSafeTimedSerializer


__all__ = ("Serializer", "BadSignature", )


class Serializer:
    # the hash function to use for the signature.
    digest_method = staticmethod(hashlib.sha1)

    # the name of the itsdangerous supported key derivation.
    key_derivation = "hmac"

    namespace = "proper.session"
    data_serializer = json

    def __init__(self, secret_key):
        signer_kwargs = {
            "key_derivation": self.key_derivation,
            "digest_method": self.digest_method,
        }
        self.s = URLSafeTimedSerializer(
            secret_key,
            salt=self.namespace,
            serializer=self.data_serializer,
            signer_kwargs=signer_kwargs,
        )

    def loads(self, str_value, max_age=None):
        return self.s.loads(str_value, max_age=max_age)

    def dumps(self, dict_value):
        return self.s.dumps(dict_value)
