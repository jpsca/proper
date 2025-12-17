import base64
import hashlib
import hmac
import typing as t
from time import time

import passlib.hash
from passlib.context import CryptContext
from passlib.utils import saslprep

from .errors import WrongHashAlgorithm
from .helpers import logger


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


def force_bytes(s, encoding="utf-8", errors="strict"):
    if isinstance(s, bytes):
        if encoding == "utf-8":
            return s
        else:
            return s.decode("utf-8", errors).encode(encoding, errors)
    return str(s).encode(encoding, errors)


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


def urlsafe_base64_encode(s: str) -> str:
    sb = s.encode()
    return base64.urlsafe_b64encode(sb).rstrip(b"\n=").decode("ascii")


def urlsafe_base64_decode(s: str) -> str:
    """
    Decode a base64 encoded string. Add back any trailing equal signs that
    might have been stripped.
    """
    sb = s.encode()
    return base64.urlsafe_b64decode(sb.ljust(len(sb) + len(sb) % 4, b"=")).decode("ascii")


class Auth:
    __slots__ = [
        "secret_keys",
        "hasher",
        "_decoy_password",
        "password_minlen",
        "password_maxlen",
        "digestmod",
    ]

    key_salt = "proper.auth"

    def __init__(
        self,
        secret_keys: list[str] | tuple[str, ...],
        *,
        hash_name: str | None = DEFAULT_HASHER,
        rounds: int | None = None,
        password_minlen: int = 5,
        password_maxlen: int = 1024,
        digestmod: str = "sha1",
    ) -> None:
        self.secret_keys = secret_keys
        self._set_hasher(hash_name or DEFAULT_HASHER, rounds)
        self._decoy_password = self.hasher.hash("!")
        self.password_minlen = password_minlen
        self.password_maxlen = password_maxlen
        self.digestmod = digestmod

    def _set_hasher(
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
        rounds = int(min(max(rounds or default_rounds, min_rounds), max_rounds))

        op = {
            "schemes": VALID_HASHERS,
            "default": hash_name,
            hash_name + "__default_rounds": rounds,
        }
        self.hasher = CryptContext(**op)

    def hash_password(self, secret: str) -> str | None:
        if secret is None:
            return None

        # Passlib recommends normalizing the unicode strings
        # used as passwords
        secret = saslprep(secret, param="password")

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
            logger.debug("User `%s` not found", login)
            self.password_is_valid("invalid", self._decoy_password)
            return None

        if not user.password:
            logger.debug("User `%s` has no password", login)
            self.password_is_valid("invalid", self._decoy_password)
            return None

        if not self.password_is_valid(password, user.password):
            logger.debug("Invalid password for user `%s`", login)
            return None

        if update_hash:
            # If the hash method has change, update the
            # hash to the new format.
            self.update_password_hash(password, user)
        return user

    def update_password_hash(self, secret: str, user: t.Any) -> None:
        new_hash = self.hash_password(secret)
        if not new_hash:
            return
        if new_hash.split("$")[:3] == user.password.split("$")[:3]:
            return
        user.pasword = new_hash

    def get_token(
        self,
        user: t.Any,
        *,
        timestamp: int | None = None,
        secret_key: str | None = None,
    ) -> str:
        u64 = urlsafe_base64_encode(str(user.id))
        timestamp = int(timestamp or time())
        digest = self._salted_hmac(
            secret_key or self.secret_keys[-1],
            user,
            str(timestamp)
        )
        return f"{u64}${to36(timestamp)}${digest}"

    def split_token(self, token: str) -> tuple[str, int, str]:
        try:
            u64, t36, digest = token.split("$", 2)
            return urlsafe_base64_decode(u64), from36(t36), digest
        except ValueError:
            return "", 0, ""

    def check_token(
        self,
        model: t.Any,
        token: str | None,
        token_life: int,
    ) -> t.Any:
        if token is None:
            return None
        user_id, timestamp, digest = self.split_token(token)
        if not (user_id and timestamp and digest):
            logger.info("Invalid token format")
            return None

        user = model.get_by_id(user_id)
        if not user:
            logger.info("Invalid token. User `%s` not found", user_id[:20])
            return None

        expired = timestamp + token_life < int(time())
        if expired:
            logger.info("Expired token")
            return None

        for secret_key in self.secret_keys:
            ref_token = self.get_token(user, timestamp=timestamp, secret_key=secret_key)
            _, _, ref_digest = self.split_token(ref_token)
            if hmac.compare_digest(digest, ref_digest):
                return user

        logger.info("Invalid token")
        return None

    # Private

    def _salted_hmac(
        self,
        secret_key: str,
        user: t.Any,
        timestamp: str = "",
    ) -> str:
        hmac_hasher = getattr(hashlib, self.digestmod)

        # If len(key_salt + secret) > block size of the hash algorithm, the above
        # line is redundant and could be replaced by key = key_salt + secret, since
        # the hmac module does the same thing for keys longer than the block size.
        # However, we need to ensure that we *always* do this.
        key = hmac_hasher(force_bytes(self.key_salt) + force_bytes(secret_key)).digest()

        value = "|".join(
            [
                # So the user.id cannot be forged
                str(user.id),
                # By using the password hash this token will be invalidated
                # automatically just by changing (or re-saving) the password.
                (user.password or "")[::2],
                # So the timestamp cannot be forged
                timestamp,
            ]
        ).encode("utf8", "ignore")

        return hmac.new(key, force_bytes(value), digestmod=hmac_hasher).hexdigest()
