import unicodedata

from proper import request, response

from [[ app_name ]].app import auth, config, db


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
            self.nfc_login = self.normalize_login(login, uform="NFC")
            return self.normalize_login(login)

    @db.validates("password")
    def validate_password(self, _key, password):
        if password:
            return auth.hash_password(password)

    @staticmethod
    def normalize_login(login="", *, uform="NFKC"):
        login = login.lower().strip()
        return unicodedata.normalize(uform, login)

    @classmethod
    def by_id(cls, pk):
        """Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        return db.s.get(cls, pk)

    @classmethod
    def by_login(cls, login):
        """Get a user by its username.
        Modify this code or overwrite in the User class to to include whatever
        scope restriction you need to add to this query.

        Required by proper.auth.Auth()
        """
        login = cls.normalize_login(login)
        return db.s.execute(
            db.select(cls).where(cls.login == login)
        ).scalars().first()

    @classmethod
    def authenticate(cls, login, password, *, update_hash=True):
        login = cls.normalize_login(login)
        return auth.authenticate(cls, login, password, update_hash=update_hash)

    @classmethod
    def authenticate_timestamped_token(cls, token):
        return auth.authenticate_timestamped_token(cls, token, config.auth.token_life)

    @classmethod
    def authenticate_session_token(cls, token):
        return auth.authenticate_session_token(cls, token)

    def sign_in(self):
        """Store in the session an unique token for the user, so it can stay
        logged between requests.
        """
        assert self.id is not None
        request.user = self
        response.session[self.SESSION_KEY] = auth.get_session_token(request.user)

    def sign_out(self):
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

    def set_new_password(self, new_password):
        self.password = new_password
        if request.user == self:
            # Password has change, so we need to updated the session too
            self.sign_in()
