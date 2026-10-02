import base64
import typing as t

import passlib.hash
from passlib.context import CryptContext
from passlib.utils import saslprep

from ..errors import WrongHashAlgorithm
from ..helpers import logger


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
a limited subset of hash functions:

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
    return base64.urlsafe_b64decode(sb + b"=" * (-len(sb) % 4)).decode("ascii")


class Auth:
    __slots__ = [
        "secret_keys",
        "hasher",
        "_decoy_password",
        "password_minlen",
        "password_maxlen",
    ]

    def __init__(
        self,
        secret_keys: list[str] | tuple[str, ...],
        *,
        hash_name: str | None = DEFAULT_HASHER,
        rounds: int | None = None,
        password_minlen: int = 5,
        password_maxlen: int = 1024,
    ) -> None:
        self.secret_keys = secret_keys
        self._set_hasher(hash_name or DEFAULT_HASHER, rounds)
        self._decoy_password = self.hasher.hash("!")
        self.password_minlen = password_minlen
        self.password_maxlen = password_maxlen

    def _set_hasher(
        self,
        hash_name: str,
        rounds: int | None = None,
    ) -> None:
        """Updates the hash algorithm and, optionally, the number of rounds
        to use.

        Raises:
            `~WrongHashAlgorithm` if new algorithm isn't one of the
            recommended options.

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

        # `deprecated` and the rounds limits are what `needs_update()` uses
        # to tell if a stored hash was made with other settings.
        op = {
            "schemes": VALID_HASHERS,
            "default": hash_name,
            "deprecated": "auto",
            hash_name + "__default_rounds": rounds,
            hash_name + "__min_rounds": rounds,
            hash_name + "__max_rounds": rounds,
        }
        self.hasher = CryptContext(**op)

    def hash_password(self, secret: str) -> str | None:
        """Hash a password that a user is setting.

        Raises:
            `ValueError` if the password is too short, too long, or has
            characters that aren't allowed in a password.

        """
        if secret is None:
            return None

        # Passlib recommends normalizing the unicode strings
        # used as passwords
        secret = saslprep(secret, param="password")

        len_secret = len(secret)
        if len_secret < self.password_minlen:
            raise ValueError(
                "Password is too short. Must have at least "
                f"{self.password_minlen} characters"
            )
        if len_secret > self.password_maxlen:
            raise ValueError(
                "Password is too long. Must have at most "
                f"{self.password_maxlen} characters"
            )

        return self.hasher.hash(secret)

    def _normalize(self, secret: str) -> str:
        """The password as `hash_password()` hashes it. One that can't be
        normalized is returned as it is, because it could be the password
        of a hash that was made somewhere else.
        """
        try:
            return saslprep(secret, param="password")
        except ValueError:
            return secret

    def password_is_valid(self, secret: str, hashed: str) -> bool:
        if secret is None or hashed is None:
            return False
        try:
            # To help preventing denial-of-service via large passwords
            # See: https://www.djangoproject.com/weblog/2013/sep/15/security/
            if len(secret) > self.password_maxlen:
                return False
            normalized = self._normalize(secret)
            if self.hasher.verify(normalized, hashed):
                return True
            # A hash made somewhere else might be of the password
            # without normalizing.
            return secret != normalized and self.hasher.verify(secret, hashed)
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

        if update_hash and self.update_password_hash(password, user):
            logger.debug("Updated the password hash of user `%s`", login)
            user.save()
        return user

    def update_password_hash(self, secret: str, user: t.Any) -> bool:
        """Replace `user.password` with a hash made with the current settings,
        if the one it has was made with another algorithm or another number
        of rounds. The user is not saved.

        `secret` must be the password of the user, already verified. Its length
        is not checked: the limits are for the passwords that are being set,
        and this one was set before.

        Returns:
            `True` if the hash was replaced.

        """
        if secret is None or not user.password:
            return False
        try:
            if not self.hasher.needs_update(user.password):
                return False
        except ValueError:
            # Not a hash of any of the known algorithms
            return False
        user.password = self.hasher.hash(self._normalize(secret))
        return True
