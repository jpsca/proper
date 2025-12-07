import typing as t

import peewee as pw
from passlib.utils import saslprep

from ...main import auth, config
from ...models.base import BaseMixin


class Authenticable(BaseMixin):
    login = pw.CharField(255, null=False, unique=True, index=True)
    password = pw.CharField(255)

    @property
    def email(self):
        return self.login

    @classmethod
    def _normalize_login(cls, login: str = ""):
        # https://engineering.atspotify.com/2013/06/creative-usernames/
        login = saslprep(login.strip()).casefold()
        return login.replace(" ", "")

    @classmethod
    def _prepare_data(cls, data) -> dict:
        password = data.get("password")
        if password:
            data["password"] = auth.hash_password(password)
        login = data.get("login", "").strip()
        if login:
            data["login"] = cls._normalize_login(login)
        return data

    @classmethod
    def create(cls, **data):
        data = cls._prepare_data(data)
        inst = cls(**data)
        inst.save(force_insert=True)
        return inst

    @classmethod
    def get_by_id(cls, pk: t.Any) -> t.Any:
        """Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        return cls.get_or_none(cls.id == pk)  # type: ignore

    @classmethod
    def get_by_login(cls, login: str) -> t.Any:
        """Get a user by its username.
        Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        login = cls._normalize_login(login)
        return cls.get_or_none(cls.login == login)  # type: ignore

    @classmethod
    def authenticate(
        cls,
        login: str,
        password: str,
        *,
        update_hash: bool = True,
    ) -> t.Any:
        login = cls._normalize_login(login)
        return auth.authenticate(cls, login, password, update_hash=update_hash)

    @classmethod
    def check_token(cls, token: str) -> t.Any:
        return auth.check_token(
            cls,
            token,
            config.AUTH_TOKEN_LIFE,
        )

    def get_token(self) -> str:
        return auth.get_token(self)

    def set_password(self, password: str | None) -> None:
        self.password = auth.hash_password(password) if password else password
