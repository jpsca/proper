from sqlalchemy import Column, String, select
from sqlalchemy.orm import validates

from ...models import dbs
from ...services.auth_services import auth, normalize_login


class Authenticable:
    __abstract__ = True

    SESSION_KEY = "_user_token"
    REDIRECT_KEY = "_redirect"
    CLEAR_SESSION_ON_SIGN_OUT = True

    login = Column(String(255), nullable=False, unique=True, index=True)
    nfc_login = Column(String(255), nullable=False)
    password = Column(String(255))

    @validates("login")
    def validate_login(self, _key, login):
        if login:
            self.nfc_login = normalize_login(login, uform="NFC")
            return normalize_login(login)

    @validates("password")
    def validate_password(self, _key, password):
        if password:
            return auth.hash_password(password)

    @classmethod
    def by_id(cls, pk):
        """Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        return dbs.get(cls, pk)

    @classmethod
    def by_login(cls, login):
        """Get a user by its username.

        Required by proper.auth.Auth()
        """
        return cls._by_login_select(login).scalars().first()

    @classmethod
    def exists(cls, login):
        return cls._by_login_select(login).exists()

    @classmethod
    def _by_login_select(cls, login):
        """Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.
        """
        login = normalize_login(login)
        return select(cls).where(cls.login == login)
