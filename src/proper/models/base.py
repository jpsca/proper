import typing as t
from collections.abc import Callable

import peewee as pw

from ..global_context import current
from ..units import MINUTES
from .scopes import ScopedSelect


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
        timed: bool = True,
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
            timed:
                `True` by default: the token records when it was made, so
                `resolve_token` can enforce a `max_age`. With `False` the
                token has no timestamp: it is the same every time for the
                same record, fingerprint and salt, and it cannot expire. It
                is only accepted by `resolve_token(..., max_age=None)`.
                Use it for stable, cacheable URLs.

        Returns:
            A URL-safe string suitable for use in links, headers, or
            query parameters.

        """
        assert current.app
        payload = {"id": str(self.get_id()), "fp": fingerprint(self)}
        salt = salt or self.__class__.__name__
        return current.app.dumps(payload, salt=salt, timed=timed)

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
        max_age: int | None = 15 * MINUTES,
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
                Use `None` for no expiration.
            salt:
                Optional namespace. The model name is used by default.

        Returns:
            The model instance if the token is valid, or None otherwise.

        """
        assert current.app
        salt = salt or cls.__name__
        if max_age is not None:
            max_age = max(max_age, 0)
        data = current.app.loads(token, max_age=max_age, salt=salt)
        if not data and max_age is None:
            # An untimed token can't prove its age, so it is only accepted
            # when the caller asks for no age limit.
            data = current.app.loads(token, salt=salt, timed=False)
        if not isinstance(data, dict) or "id" not in data:
            return None
        try:
            instance = cls.get_by_id(data["id"])
        except pw.DoesNotExist:
            return None

        fingerprint = (lambda x: None) if fingerprint is None else fingerprint
        if fingerprint(instance) == data.get("fp"):
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
