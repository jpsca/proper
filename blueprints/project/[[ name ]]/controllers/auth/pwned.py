"""Interface to the ¨Have I been pwned?" database
"""
import urllib.request
from hashlib import sha1
from http.client import HTTPException


API_URL = "https://api.pwnedpasswords.com/range/"
HTTP_OK = 200


def query_api(hprefix):
    url = f"{API_URL}{hprefix}"
    try:
        req = urllib.request.urlopen(url, timeout=1)
    except HTTPException:
        return []
    if req.status != HTTP_OK:
        return []
    return req.read().decode("utf8").split("\r\n")


def get_pwned_count(passw):
    hash = sha1(passw.encode("utf8")).hexdigest().upper()
    hprefix = hash[:5]
    hsuffix = hash[5:]
    resp = query_api(hprefix)

    for row in resp:
        suffix, num = row.split(":")
        if num == "0":
            continue
        if suffix == hsuffix:
            return int(num)
    return 0
