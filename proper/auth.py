import hashlib
import hmac
import logging
from time import time

import passlib.hash
from passlib.context import CryptContext


__all__ = ("DEFAULT_HASHER", "VALID_HASHERS", "WrongHashAlgorithm", "Auth")

DEFAULT_HASHER = "pbkdf2_sha512"

VALID_HASHERS = [
    "argon2",
    "bcrypt",
    "pbkdf2_sha512",
    "pbkdf2_sha256",
    "sha512_crypt",
    "sha256_crypt",
]

DEPRECATED_HASHERS = [
    "django_argon2",
    "django_bcrypt",
    "django_bcrypt_sha256",
    "django_pbkdf2_sha256",
    "django_pbkdf2_sha1",
    "django_salted_sha1",
    "django_salted_md5",
    "django_des_crypt",
]

WRONG_HASH_MESSAGE = """Invalid hash format.
Proper-Auth can *read* many hash methods but, for security reasons,
only generates hashes with the one you choose form a limited
subset of them:

Readable and writeable formats
-------------------------------
- {0}

Read-only formats
-------------------------------
- {1}

Read more about how to choose the right hash method for your
application here:
https://passlib.readthedocs.io/en/stable/narr/quickstart.html#choosing-a-hash

""".format(
    "\n - ".join(VALID_HASHERS),
    "\n - ".join(DEPRECATED_HASHERS),
)

logger = logging.getLogger(__name__)


class WrongHashAlgorithm(Exception):
    pass


def to36(number):
    assert int(number) >= 0, "Must be a positive integer"
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    if 0 <= number < len(alphabet):
        return alphabet[number]

    base36 = ""
    while number:
        number, i = divmod(number, 36)
        base36 = alphabet[i] + base36

    return base36 or alphabet[0]


def from36(snumber):
    snumber = snumber.upper()
    return int(snumber, 36)


class Auth:
    def __init__(
        self,
        secret_key,
        *,
        hash_name=DEFAULT_HASHER,
        rounds=None,
        password_minlen=5,
        password_maxlen=1024,
    ):
        self.secret_key = secret_key
        self.set_hasher(hash_name, rounds)
        self.password_minlen = password_minlen
        self.password_maxlen = password_maxlen

    def set_hasher(self, hash_name, rounds=None):
        """Updates the has algorithm and, optionally, the number of rounds
        to use.

        Raises:
            `~WrongHashAlgorithm` if new algorithm isn't one of the three
            recomended options.

        """
        hash_name = hash_name.replace("-", "_")
        if hash_name not in VALID_HASHERS:
            raise WrongHashAlgorithm(WRONG_HASH_MESSAGE)

        hasher = getattr(passlib.hash, hash_name)
        # Make sure all the hasher dependencies are installed, because it is an
        # easy-to-miss error.
        hasher.hash("test")

        default_rounds = getattr(hasher, "default_rounds", 1)
        min_rounds = getattr(hasher, "min_rounds", 1)
        max_rounds = getattr(hasher, "max_rounds", float("inf"))
        rounds = min(max(rounds or default_rounds, min_rounds), max_rounds)

        op = {
            "schemes": VALID_HASHERS + DEPRECATED_HASHERS,
            "deprecated": DEPRECATED_HASHERS,
            "default": hash_name,
            hash_name + "__default_rounds": rounds,
        }
        self.hasher = CryptContext(**op)
        self._set_decoy_password()

    def _set_decoy_password(self):
        self._decoy_password = self.hasher.hash("!")

    def hash_password(self, secret):
        if secret is None:
            return None

        len_secret = len(secret)
        if len_secret < self.password_minlen:
            raise ValueError(
                "Password is too short. Must have at least "
                f"{self.password_minlen} chars long"
            )
        if len_secret > self.password_maxlen:
            raise ValueError(
                "Password is too long. Must have at most "
                f"{self.password_maxlen} chars long"
            )

        return self.hasher.hash(secret)

    def password_is_valid(self, secret, hashed):
        if secret is None or hashed is None:
            return False
        try:
            # To help preventing denial-of-service via large passwords
            # See: https://www.djangoproject.com/weblog/2013/sep/15/security/
            if len(secret) > self.password_maxlen:
                return False
            return self.hasher.verify(secret, hashed)
        except ValueError:
            return False

    def get_session_token(self, user):
        key = "|".join(
            [
                # Includes the secret key, so without access to the source code,
                # fake tokens cannot be generated even if the database is compromised.
                self.secret_key,
                # So the the token is always unique for each user.
                str(user.id),
                # By using a snippet of the password hash **salt**,
                # you can logout from all other devices
                # just by changing (or re-saving) the password.
                (user.password or "").rsplit("$", 1)[0][-10:],
            ]
        )

        key = key.encode("utf8", "ignore")
        mac = hmac.new(key, msg=None, digestmod=hashlib.sha512)
        mac = mac.hexdigest()
        return f"{user.id}${mac}"

    def get_timestamped_token(self, user, timestamp):
        timestamp = int(timestamp or time())

        key = "|".join(
            [
                # Includes the secret key, so without access to the source code,
                # fake tokens cannot be generated even if the database is compromised.
                self.secret_key,
                # So the the token is always unique for each user.
                str(user.id),
                # By using a snippet of the password hash **salt**,
                # you can logout from all other devices
                # just by changing (or re-saving) the password.
                (user.password or "").rsplit("$", 1)[0][-10:],
                # So the timestamp cannot be forged
                str(timestamp),
            ]
        )

        key = key.encode("utf8", "ignore")
        mac = hmac.new(key, msg=None, digestmod=hashlib.sha512)
        mac = mac.hexdigest()
        return f"{user.id}${to36(timestamp)}${mac}"

    def update_password_hash(self, secret, user):
        new_hash = self.hash_password(secret)
        if new_hash.split("$")[:3] == user.password.split("$")[:3]:
            return
        user.pasword = new_hash

    def authenticate(self, model, login, password, *, update_hash=True):
        if login is None or password is None:
            return None

        user = model.by_login(login)
        if not user:
            logger.debug("User `{login}` not found", extra={"login": login})
            self.password_is_valid("invalid", self._decoy_password)
            return None

        if not user.password:
            logger.debug("User `{login}` has no password", extra={"login": login})
            self.password_is_valid("invalid", self._decoy_password)
            return None

        if not self.password_is_valid(password, user.password):
            logger.debug("Invalid password for user `{login}`", extra={"login": login})
            return None

        if update_hash:
            # If the hash method has change, update the
            # hash to the new format.
            self.update_password_hash(password, user)
        return user

    def authenticate_token(self, model, token, token_life=None):
        if token is None:
            return None

        if token_life:
            return self.authenticate_timestamped_token(model, token, token_life)
        return self.authenticate_session_token(model, token)

    def authenticate_session_token(self, model, token):
        if token is None:
            return None
        user_id, _ = self.split_session_token(token)
        if not user_id:
            logger.info("Invalid token format")
            return None

        user = model.by_id(user_id)
        if not user:
            logger.info(
                "Invalid token. User `{user_id}` not found",
                extra={"user_id": user_id[:20]}
            )
            return None

        if self.get_session_token(user) != token:
            logger.info("Invalid token")
            return None

        return user

    def authenticate_timestamped_token(self, model, token, token_life):
        if token is None:
            return None
        user_id, timestamp = self.split_timestamped_token(token)
        if not user_id:
            logger.info("Invalid token format")
            return None

        user = model.by_id(user_id)
        if not user:
            logger.info(
                "Invalid token. User `{user_id}` not found",
                extra={"user_id": user_id[:20]}
            )
            return None

        if self.get_timestamped_token(user, timestamp) != token:
            logger.info("Invalid token")
            return None

        expired = timestamp + token_life < int(time())
        if expired:
            logger.info("Expired token")
            return None

        return user

    def split_session_token(self, token):
        try:
            uid, mac = token.split("$", 1)
            return uid, mac
        except ValueError:
            return None, None

    def split_timestamped_token(self, token):
        try:
            uid, t36, mac = token.split("$", 2)
            return uid, from36(t36)
        except ValueError:
            return None, None
