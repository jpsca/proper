import typing as t
from hashlib import sha256

import idna
import peewee as pw
from passlib.utils import saslprep

from ...main import auth
from ...models.base import BaseModel


class Authenticable(BaseModel):
    login = pw.CharField(255, null=False, unique=True, index=True)
    password = pw.CharField(255)

    @property
    def email(self):
        return self.login

    @classmethod
    def normalize_login(cls, login: str = ""):
        # https://engineering.atspotify.com/2013/06/creative-usernames/
        login = saslprep(login.strip()).replace(" ", "")
        name, at, domain = login.rpartition("@")
        if not at or domain.isascii():
            return login.casefold()
        # An international domain is the same domain in punycode, its ASCII
        # form: `münchen.de` is `xn--mnchen-3ya.de`. IDNA 2008, as the
        # registries, so `straße.de` is not `strasse.de`, as `casefold()`
        # would make it: `idna` lowercases the domain itself.
        try:
            domain = idna.encode(domain, uts46=True).decode()
        except idna.IDNAError:
            # Not a valid domain: left as it is
            domain = domain.casefold()
        return f"{name.casefold()}@{domain}"

    @classmethod
    def _prepare_data(cls, data) -> dict:
        password = data.get("password")
        if password:
            data["password"] = auth.hash_password(password)
        login = data.get("login", "").strip()
        if login:
            data["login"] = cls.normalize_login(login)
        return data

    @classmethod
    def create(cls, **data):
        data = cls._prepare_data(data)
        inst = cls(**data)
        inst.save(force_insert=True)
        return inst

    @classmethod
    def get_by_id(cls, pk: t.Any) -> t.Any:
        """Modify this code or overwrite in the User class to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        return super().get_by_id(pk)

    @classmethod
    def get_by_login(cls, login: str) -> t.Any:
        """Get a user by its username.
        Modify this code or overwrite in the User class to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        login = cls.normalize_login(login)
        return cls.get_or_none(cls.login == login)  # type: ignore

    @classmethod
    def authenticate(
        cls,
        login: str,
        password: str,
        *,
        update_hash: bool = True,
    ) -> t.Any:
        login = cls.normalize_login(login)
        return auth.authenticate(cls, login, password, update_hash=update_hash)

    def set_password(self, password: str | None) -> None:
        self.password = auth.hash_password(password) if password else password or ""

    def generate_token_for_password_reset(self):
        """Return a value that changes when the password_reset token should
        be invalidated.

        The value is embedded in the token at generation time and compared
        against a fresh computation at resolution time. If the two differ,
        the token is treated as revoked.

        The return value must be JSON-serializable (str, int, etc.) and
        must be deterministic for a given model state - i.e., calling it
        twice on the same unchanged record must return the same result.

        It should NOT contain sensitive data, as the token payload is
        signed but not encrypted.

        Examples:
            # Invalidate when password hash changes
            lambda user: sha256(user.password.encode()).hexdigest()[:20]

            # Invalidate when email changes
            lambda user: user.email

            # One-time use (invalidate after any update)
            lambda user: str(user.updated_at)

        """
        # Invalidate when password hash changes. A digest of the hash, not a
        # piece of it: the token goes by email, signed but not encrypted.
        return sha256((self.password or "").encode()).hexdigest()[:20]
