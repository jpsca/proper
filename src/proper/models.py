import types
import typing as t
from collections.abc import Callable

import peewee as pw

from .global_context import current
from .helpers import jsonplus
from .units import MINUTES


__all__ = (
    "JSONField",
    "ScopedSelect",
    "scope",
    "ProperModel",
)


class JSONField(pw.TextField):
    """A TextField-based Peewee field that transparently
    serializes/deserializes JSON data."""

    field_type = "JSON"

    def db_value(self, value: dict | list | None) -> str | None:
        if value is None:
            return None

        ensure_ascii = getattr(self.model._meta.database, "json_ensure_ascii", True)
        if getattr(self.model._meta.database, "json_use_detailed", False):
            indent = 2
        else:
            indent = 0

        return jsonplus.dumps(value, ensure_ascii=ensure_ascii, indent=indent)

    def python_value(self, value) -> dict[str, t.Any] | list[t.Any] | None:
        if value is None:
            return None
        try:
            return jsonplus.loads(value)
        except jsonplus.JSONDecodeError:
            return None


class ScopedSelect(pw.ModelSelect):
    """ModelSelect that preserves scopes automatically.

    It adds a little overhead to every method call in exchange
    of a future-proof detection of any query-retuning method.
    However, the overhead is neligible since the queries are built once
    and the real bottleneck will always be the query *execution*.
    """

    _scopes = {}

    def _bind_scopes(self, scopes):
        self._scopes = scopes
        return self

    def __getattribute__(self, name):
        """"""
        # Resolve scopes dynamically so they always bind to the current
        # instance (important after clone() which copies __dict__).
        scopes = super().__getattribute__("_scopes")
        if scopes and name in scopes:
            return types.MethodType(scopes[name], self)

        val = super().__getattribute__(name)

        # Not callable, or is private/class - return as-is
        if name.startswith("_") or not callable(val) or isinstance(val, type):
            return val

        if not scopes:
            return val

        # Wrap the method to propagate scopes to the result
        def wrapper(*args, **kwargs):
            result = val(*args, **kwargs)
            if type(result) is pw.ModelSelect:
                result.__class__ = ScopedSelect
                result._bind_scopes(scopes)
            return result

        return wrapper


def scope(fn):
    """Tag a method as a scope."""
    fn._is_scope = True
    return fn


class ProperModel(pw.Model):
    """Base Peewee model with extra features: scope support and token generation."""

    @classmethod
    def _collect_scopes(cls):
        scopes = {}
        for name in dir(cls):
            attr = getattr(cls, name, None)
            if callable(attr) and getattr(attr, "_is_scope", False):
                scopes[name] = attr
        return scopes

    @classmethod
    def select(cls, *fields):
        query = super().select(*fields)
        scopes = cls._collect_scopes()
        if scopes:
            query.__class__ = ScopedSelect
            query._bind_scopes(scopes)
        return query

    def generate_token(
        self,
        fingerprint: Callable = (lambda x: None),
        *,
        salt: str | None = None,
    ) -> str:
        """Generate a signed, URL-safe token for this record.

        The token embeds the record's primary key and an optional
        fingerprint value, which can be used to automatically invalidate
        the token when the underlying record changes.

        Arguments:
            fingerprint:
                Function that should returns a value that changes when the token
                should be invalidated.

                The value is embedded in the token at generation time and compared
                against a fresh computation at resolution time. If the two differ,
                the token is treated as revoked.

                The return value must be JSON-serializable (str, int, etc.) and
                must be deterministic for a given model state - i.e., calling it
                twice on the same unchanged record must return the same result.

                It should NOT contain sensitive data, as the token payload is
                signed but not encrypted.

                Examples:
                    lambda user: user.password[-10:]

                    # Invalidate when email changes
                    lambda user: user.email

                    # One-time use (invalidate after any update)
                    lambda user: str(user.updated_at)

            salt:
                Optional namespace. The model name is used by default.

        Returns:
            A URL-safe string suitable for use in links, headers, or
            query parameters.

        """
        assert current.app
        payload = {"id": str(self.get_id()), "fp": fingerprint(self)}
        salt = salt or self.__class__.__name__
        return current.app.dumps(payload, salt=salt)

    def generate_token_for(self, name: str) -> str:
        """Generate a signed, URL-safe token for this record using the
        name as salt and the method `generate_token_for_NAME` as fingerprint function.
        """
        assert current.app
        fp_value = getattr(self, f"generate_token_for_{name}")()
        payload = {"id": str(self.get_id()), "fp": fp_value}
        return current.app.dumps(payload, salt=name)

    @classmethod
    def resolve_token(
        cls,
        token: str,
        fingerprint: Callable = (lambda x: None),
        *,
        max_age: int = 15 * MINUTES,
        salt: str | None = None,
    ) -> t.Any:
        """Resolve a token back into a model instance.

        Verifies the signature and expiration, loads the record by its
        primary key, and checks that the fingerprint still matches. Returns
        None if any step fails - expired, tampered, record missing, or
        fingerprint mismatch.

        Arguments:
            token:
                The token string produced by `generate_token`.
            fingerprint:
                The same callable that was used at generation time.
                Must be identical, otherwise the comparison will fail and
                the token will be treated as revoked.
            max_age:
                Maximum token age in seconds. Defaults to 15 minutes.
            salt:
                Optional namespace. The model name is used by default.

        Returns:
            The model instance if the token is valid, or None otherwise.

        """
        assert current.app
        salt = salt or cls.__name__
        data = current.app.loads(token, max_age=max_age, salt=salt)
        if not data:
            return None
        data = t.cast(dict, data)
        try:
            instance = cls.get_by_id(data["id"])
        except pw.DoesNotExist:
            return None

        fingerprint = (lambda x: None) if fingerprint is None else fingerprint
        if fingerprint(instance) == data["fp"]:
            return instance
        return None

    @classmethod
    def resolve_token_for(
        cls,
        name: str,
        token: str,
        *,
        max_age: int = 15 * MINUTES,
    ) -> t.Any:
        """Resolve a token back into a model instance using the name as salt
        and the method `generate_token_for_NAME` as fingerprint function.

        The rest of the arguments are as in `resolve_token`.
        """
        assert current.app
        data = current.app.loads(token, max_age=max_age, salt=name)
        if not data:
            return None
        data = t.cast(dict, data)
        try:
            instance = cls.get_by_id(data["id"])
        except pw.DoesNotExist:
            return None

        fingerprint = getattr(instance, f"generate_token_for_{name}")
        if fingerprint() == data["fp"]:
            return instance
        return None
