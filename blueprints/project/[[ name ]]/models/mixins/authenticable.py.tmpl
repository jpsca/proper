from datetime import datetime, timezone

from [[ name ]].adapters import db
from [[ name ]].config import config
from proper.auth import Auth


__all__ = ["Authenticable"]

auth = Auth(
    hash_name=config.auth.hash_name,
    rounds=config.auth.get("rounds"),
    password_minlen=config.auth.password_minlen,
    password_maxlen=config.auth.password_maxlen,
)


class Authenticable:
    SESSION_KEY = "_user_token"
    REDIRECT_KEY = "_redirect"
    CLEAR_SESSION_ON_SIGN_OUT = True

    login = db.Column(db.Unicode(255), nullable=False, unique=True, index=True)
    password = db.Column(db.String(255))
    last_sign_in = db.Column(db.DateTime)

    @db.validates("login")
    def __normalize_login(self, _, login):
        return self.__class__.normalize_login(login)

    @db.validates("password")
    def __hash_password(self, _, password):
        return auth.hash_password(password) if password else ""

    @classmethod
    def normalize_login(cls, login):
        # This avoids you so many support emails you wouldn't believe it.
        return (login or "").lower()

    @classmethod
    def by_id(cls, user_id):
        """Needed by auth.AuthManager. Get an user by its primary key.

        Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.
        """
        return cls.first(id=user_id)

    @classmethod
    def by_login(cls, login):
        """Needed by auth.AuthManager. Get an user by login.
        """
        login = cls.normalize_login(login)
        return cls.first(login=login)

    @classmethod
    def authenticate(cls, login, password, *, update_hash=True):
        login = cls.normalize_login(login)
        return auth.authenticate(cls, login, password, update_hash=update_hash)

    @classmethod
    def authenticate_session_token(cls, token):
        return auth.authenticate_session_token(cls, token)

    @classmethod
    def authenticate_timestamped_token(cls, token):
        return auth.authenticate_timestamped_token(cls, token, config.auth.token_life)

    def get_session_token(self):
        """Needed by auth.AuthManager.
        Makes an unique identifier for the user.
        """
        return auth.get_session_token(config.secret_key, self)

    def get_timestamped_token(self, timestamp=None):
        """Needed by auth.AuthManager.
        Makes a timestamped one-time-use token that can be used to
        identifying the user.
        """
        return auth.get_timestamped_token(config.secret_key, self, timestamp)

    def sign_in(self, req, resp):
        """Store in the session an unique token for the user, so it can stay
        logged between requests.
        """
        self.last_sign_in = datetime.now(tz=timezone.utc)
        db.commit()
        assert self.id is not None
        req.user = self
        resp.session[self.SESSION_KEY] = self.get_session_token()

    def sign_out(self, req, resp):
        req.user = None

        # The session is shared so, if you have more than
        # one model/user-type signed in at the same time,
        # you don't want to do this.
        if self.CLEAR_SESSION_ON_SIGN_OUT:
            resp.session.clear()
            return

        if self.SESSION_KEY in resp.session:
            del resp.session[self.SESSION_KEY]
        if self.REDIRECT_KEY in resp.session:
            del resp.session[self.SESSION_KEY]

    def set_password(self, password):
        self.password = password
        db.commit()

    def set_raw_password(self, password):
        """Sets the password without hashing.
        Don't use it unless you have a good reason to do so.
        """
        table = self.__table__
        db.execute(
            table.update()
            .where(table.c.id == self.id)
            .values(password=password)
        )
        db.commit()
