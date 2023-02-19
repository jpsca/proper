import unicodedata
import typing as t

from peewee import *  # noqa
from proper import request, response

from [[ app_name ]].app import auth, config, db


class Authenticable:
    SESSION_KEY: str = "_user_token"
    REDIRECT_KEY: str = "_redirect"
    CLEAR_SESSION_ON_SIGN_OUT: bool = True

    login = CharField(255, nullable=False, unique=True, index=True)
    nfc_login = CharField(255, nullable=False)
    password = CharField(255)

    @staticmethod
    def normalize_login(login="", *, uform="NFKC"):
        login = login.lower().strip()
        return unicodedata.normalize(uform, login)

    @classmethod
    def get_by_id(cls, pk: t.Any) -> "self":
        """Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        return self.get_or_none(cls.id == pk)

    @classmethod
    def get_by_login(cls, login: str) -> self | None:
        """Get a user by its username.
        Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        login = cls.normalize_login(login)
        return self.get_or_none(cls.login == login)

    @classmethod
    def authenticate(
        cls,
        login: str,
        password: str,
        *,
        update_hash: bool = True,
    ) -> self | None:
        login = cls.normalize_login(login)
        return auth.authenticate(cls, login, password, update_hash=update_hash)

    @classmethod
    def authenticate_timestamped_token(cls, token: str) -> self | None:
        return auth.authenticate_timestamped_token(
            cls,
            token,
            config.auth.token_life,
        )

    @classmethod
    def authenticate_session_token(cls, token: str) -> self | None:
        return auth.authenticate_session_token(cls, token)

    def set_login(self, login: str) -> None:
        self.nfc_login = self.normalize_login(login, uform="NFC")
        self.login = self.normalize_login(login)

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
        assert self.id is not None
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
