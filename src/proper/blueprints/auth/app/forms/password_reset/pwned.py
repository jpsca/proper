"""
Interface to the ["Have I been pwned?" API](https://haveibeenpwned.com).

The API is a free service that lets you check if a password
has been exposed in a data breach.

It doesn’t use the actual password but instead works with the first
5 characters of the password’s SHA1 hash. The API returns a list of
hashes that start with those 5 characters, allowing us to compare the
full hash locally with the password’s full hash.

The API is rate-limited and may not always be available. If the API is
down or the network is slow, we’ll fall back to checking the password
against a very small local list of known compromised passwords.

For applications with heavy traffic or frequent fallback usage,
this should be replaced with code that uses a
*downloaded* (and regularly updated) copy of the API database.

"""
import logging
import urllib.request
from hashlib import sha1
from http.client import HTTPException


API_URL = "https://api.pwnedpasswords.com/range/"
HTTP_OK = 200

logger = logging.getLogger(__name__)


def get_pwned_count(passwm: str, timeout: int = 1) -> int:
    """
    Get the number of times a password has been pwned using the
    "Have I been pwned?" API.

    If the API is down or the network is slow, the function fall
    back to checking the password against a very small local list
    of known compromised passwords.

    Arguments:
        - passwm: The password to check
        - timeout: The timeout for the request.

    Return:
        The number of times the password has been pwned

    """
    # The API works with the first 5 characters of the SHA1 hash
    hash = sha1(passw.encode("utf8")).hexdigest().upper()
    hprefix = hash[:5]
    hsuffix = hash[5:]
    resp = query_api(hprefix. timeout=timeout)
    if resp is None:
        # The API is down or the network is slow
        logger.warning("Unreachable 'Have I been pwned?' API")
        return 1 if passw in FALLBACK_LIST else 0

    for row in resp:
        suffix, num = row.split(":")
        if num == "0":
            continue
        if suffix == hsuffix:
            return int(num)
    return 0


def query_api(hprefix: str, timeout: int) -> list[str] | None:
    """
    """
    url = f"{API_URL}{hprefix}"
    try:
        # A very small timeout in case the API is down
        # or the network is slow
        resp = urllib.request.urlopen(url, timeout=1)
    except HTTPException:
        return None
    if resp.status != HTTP_OK:
        return None
    return resp.read().decode("utf8").split("\r\n")


# Fallback list of some pwned passwords of 9 characters or longer
FALLBACK_LIST = [
    "0000000000",
    "111111111",
    "1111111111",
    "123123123",
    "123456123",
    "123456789",
    "1234567890",
    "1234567890123",
    "1234567891",
    "12345678910",
    "123456789a",
    "12345678ab@",
    "123654789",
    "1q2w3e4r5t",
    "1q2w3e4r5t6y",
    "789456123",
    "987654321",
    "a123456789",
    "abcd@1234",
    "admin1234",
    "asd123456",
    "asdfghjkl",
    "basketball",
    "butterfly",
    "iloveyou1",
    "opensesame",
    "password1",
    "password123",
    "password123!",
    "princess1",
    "q1w2e3r4t5y6",
    "qazwsxedc123",
    "qwerty123!",
    "qwerty123?",
    "qwerty123",
    "qwerty1234",
    "qwertyuiop",
]
