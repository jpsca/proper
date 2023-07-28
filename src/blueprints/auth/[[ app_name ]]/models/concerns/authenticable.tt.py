import re
import unicodedata
import typing as t

from peewee import *  # type: ignore
from proper import request, response

from [[app_name]].app import auth, config
from [[app_name]].models.base import BaseMixin


RX_SPACES = re.compile(r"\s+")


class Authenticable(BaseMixin):
    SESSION_KEY: str = "_user_token"
    REDIRECT_KEY: str = "_redirect"
    CLEAR_SESSION_ON_SIGN_OUT: bool = True

    # username/email for authentication and search
    login = CharField(255, null=False, unique=True, index=True)
    # username/email for display
    nfc_login = CharField(255, null=False)

    password = CharField(255)

    def __init__(self, **kwargs):
        password = kwargs.get("password")
        if password:
           kwargs["password"] = auth.hash_password(password)
        super().__init__(**kwargs)

    @staticmethod
    def _normalize_login(login="", *, uform="NFKC"):
        # This unicode normalization MUST come first
        # https://engineering.atspotify.com/2013/06/creative-usernames/
        login = unicodedata.normalize(uform, login)
        login = login.casefold()
        return RX_SPACES.sub("", login)

    @classmethod
    def _normalize_data(cls, data, kwargs) -> dict:
        ndata = super()._normalize_data(data, kwargs)
        if "login" in ndata:
            login = ndata["login"].strip()
            ndata["login"] = cls._normalize_login(login)
            ndata["nfc_login"] = unicodedata.normalize("NFC", login)
        return ndata

    @classmethod
    def get_by_id(cls, pk: t.Any) -> t.Any:
        """Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        return cls.get_or_none(cls.id == pk) # type: ignore

    @classmethod
    def get_by_login(cls, login: str) -> t.Any:
        """Get a user by its username.
        Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        login = cls._normalize_login(login)
        return cls.get_or_none(cls.login == login) # type: ignore

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

        if request.user == self:
            # Password has change, so we need to updated the session too
            self.sign_in()

    def sign_in(self) -> None:
        """Store in the session an unique token for the user, so it can stay
        logged between requests.
        """
        assert self.id is not None # type: ignore
        request.user = self
        response.session[self.SESSION_KEY] = auth.get_session_token(request.user)

    def sign_out(self) -> None:
        request.user = None
        # The session is shared so, if you have more than
        # one model/user-type signed in at the same time,
        # you don't want to do this.
        if self.CLEAR_SESSION_ON_SIGN_OUT:
            response.session.clear()
            return

        if self.SESSION_KEY in response.session:
            del response.session[self.SESSION_KEY]
        if self.REDIRECT_KEY in response.session:
            del response.session[self.SESSION_KEY]
