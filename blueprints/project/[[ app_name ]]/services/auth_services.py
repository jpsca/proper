import unicodedata

from proper.auth import Auth

from ..config import config
from ..models import dbs


auth = Auth(
    secret_key=config.secret_key,
    hash_name=config.auth_hash_name,
    rounds=config.auth_rounds,
    password_minlen=config.auth_password_minlen,
    password_maxlen=config.auth_password_maxlen,
)


def normalize_login(login="", *, uform="NFKC"):
    login = login.lower().strip()
    return unicodedata.normalize(uform, login)


def authenticate(user_model, login, password, *, update_hash=True):
    login = normalize_login(login)
    return auth.authenticate(user_model, login, password, update_hash=update_hash)


def authenticate_timestamped_token(user_model, token):
    return auth.authenticate_timestamped_token(user_model, token, config.auth_token_life)


def authenticate_session_token(user_model, token):
    return auth.authenticate_session_token(user_model, token)


def sign_in(user, req, resp):
    """Store in the session an unique token for the user, so it can stay
    logged between requests.
    """
    assert user.id is not None
    req.user = user
    resp.session[user.SESSION_KEY] = auth.get_session_token(req.user)


def sign_out(user, req, resp):
    req.user = None
    # The session is shared so, if you have more than
    # one model/user-type signed in at the same time,
    # you don't want to do this.
    if user.CLEAR_SESSION_ON_SIGN_OUT:
        resp.session.clear()
        return

    if user.SESSION_KEY in resp.session:
        del resp.session[user.SESSION_KEY]
    if user.REDIRECT_KEY in resp.session:
        del resp.session[user.SESSION_KEY]


def set_new_password(user, new_password, *, req, resp):
    user.password = new_password
    dbs.commit
    # Password has change, so we need to updated the session too
    sign_in(user, req, resp)
