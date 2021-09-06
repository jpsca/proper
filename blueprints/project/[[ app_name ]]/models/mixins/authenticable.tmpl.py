from [[ app_name ]].models import db, dbs
from [[ app_name ]].services.auth_services import auth, normalize_login


class Authenticable:
    __abstract__ = True

    SESSION_KEY = "_user_token"
    REDIRECT_KEY = "_redirect"
    CLEAR_SESSION_ON_SIGN_OUT = True

    login = db.Column(db.String(255), nullable=False, unique=True, index=True)
    nfc_login = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255))

    @db.validates("login")
    def validate_login(self, _key, login):
        if login:
            self.nfc_login = normalize_login(login, uform="NFC")
            return normalize_login(login)

    @db.validates("password")
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
        Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        login = normalize_login(login)
        return dbs.execute(
            db.select(cls).where(cls.login == login)
        ).scalars().first()
