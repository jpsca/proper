import typing as t

import peewee as pw
from passlib.utils import saslprep
from proper import current

from app.main import auth, config
from app.models.base import BaseMixin


class Authenticable(BaseMixin):
    SESSION_KEY: str = "_user_token"
    REDIRECT_KEY: str = "_redirect"
    CLEAR_SESSION_ON_SIGN_OUT: bool = True

    login = pw.CharField(255, null=False, unique=True, index=True)
    password = pw.CharField(255)

    @property
    def email(self):
        return self.login

    @classmethod
    def _normalize_login(cls, login: str = ""):
        # https://engineering.atspotify.com/2013/06/creative-usernames/
        login = saslprep(login).casefold()
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
    def authenticate_timestamped_token(cls, token: str) -> t.Any:
        return auth.authenticate_timestamped_token(
            cls,
            token,
            config.AUTH_TOKEN_LIFE,
        )

    @classmethod
    def authenticate_session_token(cls, token: str) -> t.Any:
        return auth.authenticate_session_token(cls, token)

    def set_password(self, password: str | None) -> None:
        if password:
            self.password = auth.hash_password(password)
        else:
            self.password = password

        if current.request.user == self:
            # Password has change, so we need to updated the session too
            self.sign_in()

    def sign_in(self) -> None:
        """Store in the session an unique token for the user, so it can stay
        logged between requests.
        """
        assert self.id is not None  # type: ignore
        current.request.user = self
        current.response.session[self.SESSION_KEY] = auth.get_session_token(self)

    def sign_out(self) -> None:
        current.request.user = None
        # The session is shared so, if you have more than
        # one model/user-type signed in at the same time,
        # you don't want to do this.
        if self.CLEAR_SESSION_ON_SIGN_OUT:
            current.response.session.clear()
            return

        if self.SESSION_KEY in current.response.session:
            del current.response.session[self.SESSION_KEY]
        if self.REDIRECT_KEY in current.response.session:
            del current.response.session[self.SESSION_KEY]
