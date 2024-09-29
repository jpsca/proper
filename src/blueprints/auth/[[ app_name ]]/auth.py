import hmac
import typing as t
from time import time

import passlib.hash
from passlib.context import CryptContext

from proper.errors import WrongHashAlgorithm
from proper.helpers import logger


__all__ = ("DEFAULT_HASHER", "VALID_HASHERS", "WrongHashAlgorithm", "Auth")

DEFAULT_HASHER = "pbkdf2_sha512"

VALID_HASHERS = [
    "argon2",
    "bcrypt",
    "bcrypt_sha256",
    "pbkdf2_sha512",
    "pbkdf2_sha256",
    "sha512_crypt",
    "sha256_crypt",
]

WRONG_HASH_MESSAGE = """Invalid hash format.
For security reasons, Proper only generates hashes with
with a limited subset of hash functions:

- {0}

Read more about how to choose the right hash method for your
application here:
https://passlib.readthedocs.io/en/stable/narr/quickstart.html#choosing-a-hash

""".format(
    "\n - ".join(VALID_HASHERS)
)


def to36(number: int | str) -> str:
    if isinstance(number, str):
        number = int(number, 10)
    assert number >= 0, "Must be a positive integer"
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    if 0 <= number < len(alphabet):
        return alphabet[number]

    base36 = ""
    while number:
        number, i = divmod(number, 36)
        base36 = alphabet[i] + base36

    return base36 or alphabet[0]


def from36(snumber: str) -> int:
    snumber = snumber.upper()
    return int(snumber, 36)


class Auth:
    __slots__ = [
        "secret_keys",
        "hasher",
        "_decoy_password",
        "password_minlen",
        "password_maxlen",
        "digestmod",
    ]

    def __init__(
        self,
        secret_keys: list[str],
        *,
        hash_name: str = DEFAULT_HASHER,
        rounds: int | None = None,
        password_minlen: int = 5,
        password_maxlen: int = 1024,
        digestmod: str = "sha256",
    ) -> None:
        self.secret_keys = secret_keys
        self.set_hasher(hash_name or DEFAULT_HASHER, rounds)
        self._decoy_password = self.hasher.hash("!")
        self.password_minlen = password_minlen
        self.password_maxlen = password_maxlen
        self.digestmod = digestmod

    def set_hasher(
        self,
        hash_name: str,
        rounds: int | None = None,
    ) -> None:
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
            "schemes": VALID_HASHERS,
            "default": hash_name,
            hash_name + "__default_rounds": rounds,
        }
        self.hasher = CryptContext(**op)

    def hash_password(self, secret: str) -> str | None:
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

    def password_is_valid(self, secret: str, hashed: str) -> bool:
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

    def get_session_token(
        self,
        user: t.Any,
        *,
        secret_key: str | None = None,
    ) -> str:
        secret_key = secret_key or self.secret_keys[-1]
        digest = self._get_hmac_digest(secret_key, user)
        return f"{user.id}${digest}"

    def get_timestamped_token(
        self,
        user: t.Any,
        timestamp: int | None = None,
        *,
        secret_key: str | None = None,
    ) -> str:
        timestamp = int(timestamp or time())
        secret_key = secret_key or self.secret_keys[-1]
        digest = self._get_hmac_digest(secret_key, user, str(timestamp))
        return f"{user.id}${to36(timestamp)}${digest}"

    def update_password_hash(self, secret: str, user: t.Any) -> None:
        new_hash = self.hash_password(secret)
        if not new_hash:
            return
        if new_hash.split("$")[:3] == user.password.split("$")[:3]:
            return
        user.pasword = new_hash

    def authenticate(
        self,
        model: t.Any,
        login: str,
        password: str,
        *,
        update_hash: bool = True,
    ) -> t.Any:
        if login is None or password is None:
            return None

        user = model.get_by_login(login)
        if not user:
            logger.debug(f"User `{login}` not found")
            self.password_is_valid("invalid", self._decoy_password)
            return None

        if not user.password:
            logger.debug(f"User `{login}` has no password")
            self.password_is_valid("invalid", self._decoy_password)
            return None

        if not self.password_is_valid(password, user.password):
            logger.debug(f"Invalid password for user `{login}`")
            return None

        if update_hash:
            # If the hash method has change, update the
            # hash to the new format.
            self.update_password_hash(password, user)
        return user

    def authenticate_token(
        self,
        model: t.Any,
        token: str | None,
        token_life: int | None = None,
    ) -> t.Any:
        if token is None:
            return None
        if token_life:
            return self.authenticate_timestamped_token(model, token, token_life)
        return self.authenticate_session_token(model, token)

    def authenticate_session_token(
        self,
        model: t.Any,
        token: str | None,
    ) -> t.Any:
        if token is None:
            return None
        user_id, digest = self._split_session_token(token)
        if not (user_id and digest):
            logger.info("Invalid token format")
            return None

        user = model.get_by_id(user_id)
        if not user:
            logger.info(f"Invalid token. User `{user_id[:20]}` not found")
            return None

        for secret_key in self.secret_keys:
            ref_token = self.get_session_token(user, secret_key=secret_key)
            _, ref_digest = self._split_session_token(ref_token)
            if hmac.compare_digest(digest, ref_digest):
                return user

        logger.info("Invalid token")
        return None

    def authenticate_timestamped_token(
        self,
        model: t.Any,
        token: str | None,
        token_life: int,
    ) -> t.Any:
        if token is None:
            return None
        user_id, timestamp, digest = self._split_timestamped_token(token)
        if not (user_id and timestamp and digest):
            logger.info("Invalid token format")
            return None

        user = model.get_by_id(user_id)
        if not user:
            logger.info(f"Invalid token. User `{user_id[:20]}` not found")
            return None

        expired = timestamp + token_life < int(time())
        if expired:
            logger.info("Expired token")
            return None

        for secret_key in self.secret_keys:
            ref_token = self.get_timestamped_token(
                user, timestamp, secret_key=secret_key
            )
            _, _, ref_digest = self._split_timestamped_token(ref_token)
            if hmac.compare_digest(digest, ref_digest):
                return user

        logger.info("Invalid token")
        return None

    # Private

    def _get_hmac_digest(
        self,
        secret_key: str,
        user: t.Any,
        timestamp: str = "",
    ) -> str:
        key = "|".join(
            [
                # Includes the secret key, so without access to the source code,
                # fake tokens cannot be generated even if the database is compromised.
                secret_key,
                # By using a snippet of the password hash **salt**,
                # you can logout from all other devices
                # just by changing (or re-saving) the password.
                (user.password or "").rsplit("$", 1)[0][-10:],
                # So the timestamp cannot be forged
                timestamp,
            ]
        ).encode("utf8", "ignore")
        msg = bytes(user.id)
        digest = self.digestmod
        return hmac.digest(key, msg, digest).hex()

    def _split_session_token(self, token: str) -> tuple[str, str]:
        try:
            uid, digest = token.split("$", 1)
            return uid, digest
        except ValueError:
            return "", ""

    def _split_timestamped_token(self, token: str) -> tuple[str, int, str]:
        try:
            uid, t36, digest = token.split("$", 2)
            return uid, from36(t36), digest
        except ValueError:
            return "", 0, ""
