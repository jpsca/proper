import datetime
import time

import pytest

from proper import App, current
from proper.core.request import Request
from proper.core.request.formparser import (
    _safe_decode,
    parse_json,
    parse_options_header,
    parse_query_string,
)
from proper.core.request.headers import (
    parse_date,
    parse_host,
    parse_multivalue,
    parse_request_id,
    split_forwarded,
)
from proper.errors import (
    InvalidHeader,
    MultipartError,
    UriTooLong,
)
from proper.test_client import make_test_request


class TestParseOptionsHeader:
    def test_empty(self):
        ct, opts = parse_options_header("")
        assert ct == ""
        assert opts == {}

    def test_simple(self):
        ct, opts = parse_options_header("text/html")
        assert ct == "text/html"

    def test_with_params(self):
        ct, opts = parse_options_header("text/html; charset=utf-8")
        assert ct == "text/html"
        assert opts["charset"] == "utf-8"

    def test_multipart_boundary(self):
        ct, opts = parse_options_header(
            "multipart/form-data; boundary=----WebKitFormBoundary"
        )
        assert ct == "multipart/form-data"
        assert opts["boundary"] == "----WebKitFormBoundary"

    def test_existing_options_dict(self):
        existing = {"extra": "value"}
        ct, opts = parse_options_header("text/plain", options=existing)
        assert opts["extra"] == "value"
        assert opts is existing

    @pytest.mark.parametrize(
        "header",
        [
            "Multipart/Form-Data; Boundary=x",
            "MULTIPART/FORM-DATA; BOUNDARY=x",
            " multipart/form-data ;boundary=x",
        ],
    )
    def test_media_type_and_parameter_names_are_case_insensitive(self, header):
        """RFC 9110 §8.3.1: the type, subtype and parameter names are
        case-insensitive. The value keeps its case."""
        ct, opts = parse_options_header(header)
        assert ct == "multipart/form-data"
        assert opts == {"boundary": "x"}


class TestParseQueryString:
    def test_simple(self):
        result = parse_query_string("a=1&b=2")
        assert result.get("a") == "1"
        assert result.get("b") == "2"

    def test_empty(self):
        result = parse_query_string("")
        assert len(result) == 0

    def test_blank_values(self):
        result = parse_query_string("key=")
        assert result.get("key") == ""

    def test_max_query_size(self):
        with pytest.raises(UriTooLong):
            parse_query_string("x" * 100, max_query_size=10)

    def test_encoding(self):
        result = parse_query_string("name=%C3%A9", encoding="utf-8")
        assert result.get("name") == "\u00e9"


class TestParseJson:
    def test_valid(self):
        result = parse_json('{"key": "value"}')
        assert result.get("key") == "value"

    def test_invalid_strict(self):
        with pytest.raises(MultipartError):
            parse_json("not json")

    def test_invalid_non_strict(self):
        result = parse_json("not json", strict=False)
        assert len(result) == 0

    @pytest.mark.parametrize(
        "content",
        [
            "[1, 2]",
            '[["a", 1]]',
            '["ab"]',
            "[]",
            '"x"',
            "3",
            "true",
            "null",
        ],
    )
    def test_not_an_object_gives_an_empty_form(self, content):
        """Only the members of an object are form fields. Any other JSON
        value is valid but has no fields; the controller can read it from
        `request.body`."""
        result = parse_json(content)
        assert len(result) == 0


class TestSafeDecode:
    def test_utf8(self):
        assert _safe_decode(b"hello", "utf-8") == "hello"

    def test_latin1_fallback(self):
        raw = b"\xe9"
        result = _safe_decode(raw, "utf-8")
        assert result == raw.decode("latin-1")

    def test_bad_codec_fallback(self):
        result = _safe_decode(b"hello", "nonexistent-codec")
        assert result == "hello"


class TestParseRequestId:
    def test_none_returns_none(self):
        assert parse_request_id(None) is None

    def test_simple_id(self):
        assert parse_request_id("abc-123") == "abc-123"

    def test_hyphens_preserved(self):
        """Regression: hyphens must not be stripped as non-ASCII."""
        rid = "req-abc-def-123"
        assert parse_request_id(rid) == rid

    def test_non_ascii_stripped(self):
        assert parse_request_id("abc\u00e9def") == "abcdef"

    def test_truncated_to_max_length(self):
        long_id = "x" * 300
        result = parse_request_id(long_id)
        assert result and len(result) == 200


# ----


def _make_request(url="/", method="GET", **kw):
    return make_test_request(url, method=method, **kw)


def test_method_and_path():
    req = _make_request("/hello", method="POST")
    assert req.method == "POST"
    assert req.request_method == "POST"
    assert req.path == "/hello"


def test_content_type():
    req = _make_request("/", headers=[("content-type", "application/json")])
    assert req.content_type == "application/json"


def test_content_length():
    req = _make_request("/", headers=[("content-length", "42")])
    assert req.content_length == 42


def test_content_length_zero():
    req = _make_request("/")
    assert req.content_length == 0


def test_content_length_invalid():
    with pytest.raises(InvalidHeader, match="number"):
        _make_request("/", headers=[("content-length", "abc")])


def test_content_length_negative():
    with pytest.raises(InvalidHeader, match="positive"):
        _make_request("/", headers=[("content-length", "-1")])


def test_accept():
    req = _make_request("/", headers=[("accept", "text/html,application/json;q=0.5")])
    assert req.accept[0] == "text/html"
    assert req.accept[1] == "application/json"


def test_accept_encoding():
    req = _make_request("/", headers=[("accept-encoding", "gzip,deflate;q=0.5")])
    assert req.accept_encoding[0] == "gzip"


def test_accept_language():
    req = _make_request("/", headers=[("accept-language", "en-US,fr;q=0.5")])
    assert req.accept_language[0] == "en_US"


def test_cookies():
    req = _make_request("/", headers=[("cookie", "a=1; b=2")])
    assert req.cookies["a"] == "1"
    assert req.cookies["b"] == "2"


def test_cookies_multiple_headers():
    req = _make_request("/", headers=[("cookie", "a=1"), ("cookie", "b=2")])
    assert req.cookies["a"] == "1"
    assert req.cookies["b"] == "2"


def test_cookie_alias():
    req = _make_request("/", headers=[("cookie", "a=1")])
    assert req.cookie == req.cookies


# https://www.rfc-editor.org/info/rfc9110/#section-5.6.7
@pytest.mark.parametrize("value", [
    "Sun, 06 Nov 1994 08:49:37 GMT",   # IMF-fixdate
    "Sunday, 06-Nov-94 08:49:37 GMT",  # obsolete RFC 850 format
    "Sun Nov  6 08:49:37 1994",        # ANSI C's asctime() format
])
def test_date_header(value):
    req = _make_request("/", headers=[("date", value)])
    assert req.date == datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)


def test_date_header_missing():
    req = _make_request("/")
    assert req.date is None


@pytest.mark.parametrize(
    "value",
    [
        "garbage",
        "",
        "99999999999999999999",
        # Not in an RFC 9110 form (and the offset moves them out of range).
        "Fri, 31 Dec 9999 23:59:59 -0100",
        "9999-12-31T23:59:59-01:00",
        "0001-01-01T00:30:00+01:00",
    ],
)
def test_invalid_date_is_ignored(value):
    """RFC 9110 §13.1.3: a recipient MUST ignore an invalid date."""
    req = _make_request("/", headers=[("date", value), ("if-modified-since", value)])
    assert req.date is None
    assert req.if_modified_since is None


@pytest.fixture()
def local_time_zone_not_utc(monkeypatch):
    """A local time zone five hours behind UTC, so a date read as local
    time doesn't pass for UTC when the tests run with `TZ=UTC`."""
    monkeypatch.setenv("TZ", "EST5")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.usefixtures("local_time_zone_not_utc")
def test_date_without_a_time_zone_is_utc():
    req = _make_request("/", headers=[("date", "Sun Nov  6 08:49:37 1994")])
    assert req.date == datetime.datetime(
        1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc
    )


UTC = datetime.timezone.utc


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Sun, 06 Nov 1994 08:49:37 GMT", (1994, 11, 6, 8, 49, 37)),
        ("Sat, 01 Jan 0001 00:00:00 GMT", (1, 1, 1, 0, 0, 0)),
        ("Fri, 31 Dec 9999 23:59:59 GMT", (9999, 12, 31, 23, 59, 59)),
        ("Thu, 29 Feb 2024 12:00:00 GMT", (2024, 2, 29, 12, 0, 0)),
        # Second 60 is valid at any time (the grammar of RFC 9110 §5.6.7
        # allows 00 to 60); `datetime` has no second 60, so it is read as
        # second 59.
        ("Sat, 31 Dec 2016 23:59:60 GMT", (2016, 12, 31, 23, 59, 59)),
        ("Sun, 06 Nov 1994 08:49:60 GMT", (1994, 11, 6, 8, 49, 59)),
        ("Sunday, 06-Nov-94 08:49:60 GMT", (1994, 11, 6, 8, 49, 59)),
        ("Sun Nov  6 08:49:60 1994", (1994, 11, 6, 8, 49, 59)),
        # Recipients don't check the day name against the date.
        ("Mon, 06 Nov 1994 08:49:37 GMT", (1994, 11, 6, 8, 49, 37)),
        ("Monday, 06-Nov-94 08:49:37 GMT", (1994, 11, 6, 8, 49, 37)),
        ("Sun Nov 06 08:49:37 1994", (1994, 11, 6, 8, 49, 37)),
        ("Sun Nov 16 08:49:37 1994", (1994, 11, 16, 8, 49, 37)),
        ("Sun Nov  6 08:49:37 1994", (1994, 11, 6, 8, 49, 37)),
    ],
)
def test_parse_date_rfc9110_forms(value, expected):
    assert parse_date(value) == datetime.datetime(*expected, tzinfo=UTC)


@pytest.mark.parametrize(
    "value",
    [
        # Dropped: forms that are not one of the three of RFC 9110 §5.6.7.
        "Sun, 06 Nov 1994 10:49:37 +0200",
        "Sun, 06 Nov 1994 08:49:37 +0000",
        "Sun, 06 Nov 1994 08:49:37 UTC",
        "Sun, 06 Nov 1994 08:49:37 UT",
        "Sun, 6 Nov 1994 08:49:37 GMT",
        "06 Nov 1994 08:49:37 GMT",
        "Sun, 06 Nov 94 08:49:37 GMT",
        "Sun, 06 November 1994 08:49:37 GMT",
        "Sun, 06 Nov 1994 08:49 GMT",
        "1994-11-06T08:49:37Z",
        "1994-11-06T08:49:37+00:00",
        "1994-11-06 08:49:37",
        "1994-11-06",
        "Nov 6 1994",
        "6 Nov 1994",
        "784111777",
        "Sun Nov 6 08:49:37 1994",
        "Sun Nov  6 08:49:37 1994 GMT",
        "Sunday, 06-Nov-1994 08:49:37 GMT",
        "Sun, 06-Nov-94 08:49:37 GMT",
        "Sunday, 06 Nov 94 08:49:37 GMT",
        "Sunday, 06-Nov-94 08:49:37 +0000",
        # Day and month names are case-sensitive.
        "sun, 06 Nov 1994 08:49:37 GMT",
        "SUN, 06 Nov 1994 08:49:37 GMT",
        "Sun, 06 nov 1994 08:49:37 GMT",
        "Sun, 06 NOV 1994 08:49:37 GMT",
        "Sun, 06 Nov 1994 08:49:37 gmt",
        "sunday, 06-Nov-94 08:49:37 GMT",
        "Sun nov  6 08:49:37 1994",
        "Sund, 06 Nov 1994 08:49:37 GMT",
        "Sunday, 06-Nov-94 08:49:37 GMT ",
        # Missing GMT.
        "Sun, 06 Nov 1994 08:49:37",
        "Sunday, 06-Nov-94 08:49:37",
        # Extra or missing spaces.
        " Sun, 06 Nov 1994 08:49:37 GMT",
        "Sun, 06 Nov 1994 08:49:37 GMT ",
        "Sun,  06 Nov 1994 08:49:37 GMT",
        "Sun, 06  Nov 1994 08:49:37 GMT",
        "Sun, 06 Nov 1994  08:49:37 GMT",
        "Sun,06 Nov 1994 08:49:37 GMT",
        "Sun, 06 Nov 1994 08:49:37GMT",
        "Sun Nov   6 08:49:37 1994",
        "Sun  Nov  6 08:49:37 1994",
        "Sun Nov  6 08:49:37  1994",
        "Sun\tNov  6 08:49:37 1994",
        # Out-of-range fields.
        "Sun, 00 Nov 1994 08:49:37 GMT",
        "Sun, 31 Nov 1994 08:49:37 GMT",
        "Sun, 29 Feb 2023 08:49:37 GMT",
        "Sun, 06 Nov 0000 08:49:37 GMT",
        "Sun, 06 Nov 1994 24:00:00 GMT",
        "Sun, 06 Nov 1994 08:60:37 GMT",
        "Sun, 06 Nov 1994 08:49:61 GMT",
        "Sunday, 32-Nov-94 08:49:37 GMT",
        "Sun Nov  0 08:49:37 1994",
        "Sun Nov 31 08:49:37 1994",
        # Digits that are not ASCII.
        "Sun, \u0660\u0666 Nov 1994 08:49:37 GMT",
        "Sun, 06 Nov 1994 08:49:37 GMT\n",
    ],
)
def test_parse_date_other_forms_are_ignored(value):
    assert parse_date(value) is None


def test_parse_date_none():
    assert parse_date(None) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        # RFC 9110 §5.6.7: a two-digit year that appears to be more than 50
        # years in the future is the most recent past year with those digits.
        ("Sunday, 06-Nov-94 08:49:37 GMT", 1994),
        ("Thursday, 08-Oct-26 12:00:00 GMT", 2026),
        ("Friday, 08-Oct-76 12:00:00 GMT", 2076),
        ("Friday, 08-Oct-76 12:00:01 GMT", 1976),
        ("Friday, 09-Oct-76 00:00:00 GMT", 1976),
        ("Saturday, 01-Jan-00 00:00:00 GMT", 2000),
        ("Saturday, 01-Jan-77 00:00:00 GMT", 1977),
        ("Saturday, 01-Jan-99 00:00:00 GMT", 1999),
    ],
)
def test_parse_date_rfc850_two_digit_year(value, expected):
    now = datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)
    assert parse_date(value, now=now).year == expected


@pytest.mark.parametrize(
    "now_year, value, expected",
    [
        # RFC 9110 §5.6.7: the year with those last two digits in this
        # century, the next one or the one before: the latest one that is
        # not more than 50 years after `now` (`now_year`-10-08 12:00:00).
        (2026, "08-Oct-76 12:00:00", 2076),  # exactly 50 years ahead
        (2026, "08-Oct-76 12:00:01", 1976),  # one second more
        (2026, "08-Oct-77 12:00:00", 1977),  # 2077 is 51 years ahead
        (2026, "08-Oct-26 12:00:00", 2026),
        (2026, "08-Oct-25 12:00:00", 2025),
        (2026, "08-Oct-00 12:00:00", 2000),
        (2049, "08-Oct-99 12:00:00", 2099),  # exactly 50 years ahead
        (2049, "08-Oct-99 12:00:01", 1999),
        (2049, "08-Oct-98 12:00:00", 2098),
        (2049, "08-Oct-00 12:00:00", 2000),  # 2100 is 51 years ahead
        (2050, "08-Oct-00 12:00:00", 2100),  # exactly 50 years ahead
        (2050, "08-Oct-00 12:00:01", 2000),
        (2050, "08-Oct-01 12:00:00", 2001),  # 2101 is 51 years ahead
        (2050, "08-Oct-50 12:00:00", 2050),
        (2050, "08-Oct-99 12:00:00", 2099),
        (2051, "08-Oct-01 12:00:00", 2101),  # exactly 50 years ahead
        (2051, "08-Oct-01 12:00:01", 2001),
        (2051, "08-Oct-02 12:00:00", 2002),  # 2102 is 51 years ahead
        (2051, "08-Oct-00 12:00:00", 2100),  # 49 years ahead
        (2051, "08-Oct-51 12:00:00", 2051),
        (2051, "08-Oct-99 12:00:00", 2099),
        (2075, "08-Oct-25 12:00:00", 2125),  # exactly 50 years ahead
        (2075, "08-Oct-25 12:00:01", 2025),
        (2075, "08-Oct-26 12:00:00", 2026),  # 2126 is 51 years ahead
        (2075, "08-Oct-24 12:00:00", 2124),
        (2075, "08-Oct-00 12:00:00", 2100),
        (2075, "08-Oct-75 12:00:00", 2075),
        (2075, "08-Oct-76 12:00:00", 2076),
        (2090, "08-Oct-40 12:00:00", 2140),  # exactly 50 years ahead
        (2090, "08-Oct-40 12:00:01", 2040),
        (2090, "08-Oct-41 12:00:00", 2041),  # 2141 is 51 years ahead
        (2090, "08-Oct-39 12:00:00", 2139),
        (2090, "08-Oct-00 12:00:00", 2100),
        (2090, "08-Oct-89 12:00:00", 2089),
        (2090, "08-Oct-91 12:00:00", 2091),
        (2099, "08-Oct-49 12:00:00", 2149),  # exactly 50 years ahead
        (2099, "08-Oct-49 12:00:01", 2049),
        (2099, "08-Oct-50 12:00:00", 2050),  # 2150 is 51 years ahead
        (2099, "08-Oct-00 12:00:00", 2100),
        (2099, "08-Oct-98 12:00:00", 2098),
        (2099, "08-Oct-99 12:00:00", 2099),
    ],
)
def test_parse_date_rfc850_two_digit_year_in_three_centuries(now_year, value, expected):
    now = datetime.datetime(now_year, 10, 8, 12, 0, 0, tzinfo=UTC)
    # The day name is not checked against the date.
    assert parse_date(f"Monday, {value} GMT", now=now).year == expected


@pytest.mark.parametrize(
    "now, value, expected",
    [
        # The examples of the CHANGELOG: the year can depend on the day...
        ((2026, 10, 8, 12, 0, 0), "08-Oct-76 12:00:00", 2076),
        ((2026, 10, 8, 12, 0, 0), "08-Oct-76 12:00:01", 1976),
        ((2026, 10, 8, 12, 0, 0), "09-Oct-76 00:00:00", 1976),
        # ...but `77` is 1977 throughout 2026...
        ((2026, 1, 1, 0, 0, 0), "01-Jan-77 00:00:00", 1977),
        ((2026, 12, 31, 23, 59, 59), "01-Jan-77 00:00:00", 1977),
        ((2026, 1, 1, 0, 0, 0), "31-Dec-77 23:59:59", 1977),
        # ...and `00` is 2100 throughout 2051.
        ((2051, 1, 1, 0, 0, 0), "31-Dec-00 23:59:59", 2100),
        ((2051, 12, 31, 23, 59, 59), "01-Jan-00 00:00:00", 2100),
        # ...except `29-Feb-00`, which is 2000: 2100 has no 29 February.
        ((2051, 1, 1, 0, 0, 0), "29-Feb-00 00:00:00", 2000),
    ],
)
def test_parse_date_rfc850_two_digit_year_changelog_examples(now, value, expected):
    now = datetime.datetime(*now, tzinfo=UTC)
    assert parse_date(f"Monday, {value} GMT", now=now).year == expected


@pytest.mark.parametrize(
    "now_year, value, expected",
    [
        # A year without that date is skipped: the latest year that has it.
        (2026, "29-Feb-00 00:00:00", datetime.datetime(2000, 2, 29, tzinfo=UTC)),
        (2051, "29-Feb-00 00:00:00", datetime.datetime(2000, 2, 29, tzinfo=UTC)),
        (2051, "28-Feb-00 00:00:00", datetime.datetime(2100, 2, 28, tzinfo=UTC)),
        # 2200 and 2100 have no 29 February, 2000 has.
        (2150, "29-Feb-00 00:00:00", datetime.datetime(2000, 2, 29, tzinfo=UTC)),
        (2051, "29-Feb-04 00:00:00", datetime.datetime(2004, 2, 29, tzinfo=UTC)),
        (2051, "29-Feb-48 00:00:00", datetime.datetime(2048, 2, 29, tzinfo=UTC)),
        (2051, "29-Feb-96 00:00:00", datetime.datetime(2096, 2, 29, tzinfo=UTC)),
        # No year with those last two digits has that date.
        (2051, "29-Feb-01 00:00:00", None),
        (2051, "31-Apr-00 00:00:00", None),
    ],
)
def test_parse_date_rfc850_two_digit_year_skips_a_year_without_the_date(
    now_year, value, expected
):
    now = datetime.datetime(now_year, 1, 1, tzinfo=UTC)
    assert parse_date(f"Monday, {value} GMT", now=now) == expected


@pytest.mark.parametrize(
    "now, value, expected",
    [
        # The limits of the CHANGELOG's range where `29-Feb-00` is None:
        # from 1 January 2200 to 28 February 2350, whatever the time.
        ((2199, 12, 31, 23, 59, 59), "29-Feb-00 00:00:00", 2000),
        ((2200, 1, 1, 0, 0, 0), "29-Feb-00 00:00:00", None),
        ((2200, 1, 1, 0, 0, 0), "29-Feb-00 23:59:59", None),
        ((2299, 12, 31, 23, 59, 59), "29-Feb-00 00:00:00", None),
        ((2300, 1, 1, 0, 0, 0), "29-Feb-00 00:00:00", None),
        ((2350, 2, 28, 0, 0, 0), "29-Feb-00 00:00:00", None),
        ((2350, 2, 28, 23, 59, 59), "29-Feb-00 00:00:00", None),
        # 29 February 2400 is then not more than 50 years ahead.
        ((2350, 3, 1, 0, 0, 0), "29-Feb-00 00:00:00", 2400),
        ((2350, 3, 1, 0, 0, 0), "29-Feb-00 23:59:59", 2400),
    ],
)
def test_parse_date_rfc850_two_digit_year_none_range(now, value, expected):
    now = datetime.datetime(*now, tzinfo=UTC)
    result = parse_date(f"Monday, {value} GMT", now=now)
    assert (result and result.year) == expected


@pytest.mark.parametrize("offset_hours", [-5, 0, 5, 14, -12])
def test_parse_date_rfc850_two_digit_year_now_in_another_timezone(offset_hours):
    # The same instant gives the same year, whatever the timezone of `now`.
    now_utc = datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)
    now = now_utc.astimezone(
        datetime.timezone(datetime.timedelta(hours=offset_hours))
    )
    assert now == now_utc
    assert parse_date("Friday, 08-Oct-76 12:00:00 GMT", now=now).year == 2076
    assert parse_date("Friday, 08-Oct-76 12:00:01 GMT", now=now).year == 1976
    # At UTC-5, `now` reads 07:00; the limit is still 2076-10-08 12:00 UTC.
    assert parse_date("Friday, 08-Oct-76 08:00:00 GMT", now=now).year == 2076


def test_parse_date_rfc850_two_digit_year_naive_now_is_utc():
    now = datetime.datetime(2026, 10, 8, 12, 0, 0)
    assert parse_date("Friday, 08-Oct-76 12:00:00 GMT", now=now).year == 2076
    assert parse_date("Friday, 08-Oct-76 12:00:01 GMT", now=now).year == 1976


def test_parse_date_rfc850_two_digit_year_uses_the_current_date(monkeypatch):
    # The clock is read once, here, so the test cannot see two different
    # years (across New Year UTC); parse_date's default `now` gets this
    # same reading of `datetime.now`.
    clock = datetime.datetime.now(UTC)
    calls = []

    class Clock(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(tz)
            return clock

    monkeypatch.setattr("proper.core.request.headers.datetime", Clock)
    year = clock.year
    future = (year + 49) % 100
    past = (year + 51) % 100
    assert parse_date(f"Monday, 01-Jan-{future:02d} 00:00:00 GMT").year == year + 49
    assert parse_date(f"Monday, 01-Jan-{past:02d} 00:00:00 GMT").year == year - 49
    assert calls == [UTC, UTC]


def test_parse_date_rfc850_two_digit_year_out_of_range():
    # At the ends of `datetime`'s range.
    now = datetime.datetime(9999, 1, 1, tzinfo=UTC)
    assert parse_date("Monday, 01-Jan-99 00:00:00 GMT", now=now) == (
        datetime.datetime(9999, 1, 1, tzinfo=UTC)
    )
    now = datetime.datetime(1, 1, 1, tzinfo=UTC)
    assert parse_date("Monday, 01-Jan-99 00:00:00 GMT", now=now) is None


def test_default_port_http():
    req = _make_request("http://example.com/")
    assert req.default_port == 80


def test_default_port_https():
    req = _make_request("https://example.com/")
    assert req.default_port == 443


def test_format_html():
    req = _make_request("/", headers=[("accept", "text/html")])
    assert req.format == "html"


def test_format_json():
    req = _make_request("/", headers=[("accept", "application/json")])
    assert req.format == "json"


def test_format_wildcard_default():
    req = _make_request("/", headers=[("accept", "*/*")])
    assert req.format == "html"


def test_format_no_accept():
    req = _make_request("/")
    assert req.format == "html"


def test_forwarded():
    req = _make_request(
        "/", headers=[("forwarded", "for=192.0.2.60;proto=http;by=203.0.113.43")]
    )
    assert req.forwarded[0]["for"] == "192.0.2.60"


def test_host_with_port_default():
    req = _make_request("http://example.com/")
    assert req.host_with_port == "example.com"


def test_host_with_port_non_default():
    req = _make_request("http://example.com:9090/")
    assert req.host_with_port == "example.com:9090"


def test_if_none_match():
    req = _make_request("/", headers=[("if-none-match", '"etag1", "etag2"')])
    assert '"etag1"' in req.if_none_match
    assert '"etag2"' in req.if_none_match


# https://www.rfc-editor.org/info/rfc9110/#section-5.6.7
@pytest.mark.parametrize("value", [
    "Sun, 06 Nov 1994 08:49:37 GMT",   # IMF-fixdate
    "Sunday, 06-Nov-94 08:49:37 GMT",  # obsolete RFC 850 format
    "Sun Nov  6 08:49:37 1994",        # ANSI C's asctime() format
])
def test_if_modified_since(value):
    req = _make_request("/", headers=[("if-modified-since", value)])
    assert req.if_modified_since == datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)


def test_if_modified_since_missing():
    req = _make_request("/")
    assert req.if_modified_since is None


def test_is_get():
    assert _make_request("/", method="GET").is_get is True
    assert _make_request("/", method="POST").is_get is False


def test_is_head():
    assert _make_request("/", method="HEAD").is_head is True


def test_is_post():
    assert _make_request("/", method="POST").is_post is True


def test_is_put():
    assert _make_request("/", method="PUT").is_put is True


def test_is_patch():
    assert _make_request("/", method="PATCH").is_patch is True


def test_is_delete():
    assert _make_request("/", method="DELETE").is_delete is True


def test_is_secure_http():
    req = _make_request("http://example.com/")
    assert req.is_secure is False


def test_is_secure_https():
    req = _make_request("https://example.com/")
    assert req.is_secure is True


def test_is_ssl_alias():
    req = _make_request("https://example.com/")
    assert req.is_ssl is True


def test_is_xhr():
    req = _make_request("/", headers=[("x-requested-with", "XMLHttpRequest")])
    assert req.is_xhr is True


def test_is_xhr_false():
    req = _make_request("/")
    assert req.is_xhr is False


def test_turbo_frame():
    req = _make_request("/", headers=[("turbo-frame", "messages")])
    assert req.turbo_frame == "messages"


def test_turbo_frame_none():
    req = _make_request("/")
    assert req.turbo_frame is None


def test_turbo_stream():
    req = _make_request(
        "/", headers=[("accept", "text/vnd.turbo-stream.html, text/html")]
    )
    assert req.turbo_stream is True


def test_turbo_stream_false():
    req = _make_request("/", headers=[("accept", "text/html")])
    assert req.turbo_stream is False


def test_port_is_default():
    assert _make_request("http://example.com/").port_is_default is True
    assert _make_request("http://example.com:9090/").port_is_default is False


def test_port_string():
    assert _make_request("http://example.com/").port_string == ""
    assert _make_request("http://example.com:9090/").port_string == ":9090"


# The peer of a request through a local reverse proxy.
LOCAL_PROXY = ("127.0.0.1", 50000)


@pytest.fixture()
def no_current_app():
    """A request built without an app uses `current.app`, whatever app an
    earlier test left there, and its `TRUSTED_PROXIES`. Start without one,
    so those requests use the default list, and put back the one before
    (`App()` makes itself `current.app`)."""
    previous = current.app
    current.app = None
    yield
    current.app = previous


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_from_forwarded():
    req = _make_request("/", headers=[("forwarded", "for=1.2.3.4")], client=LOCAL_PROXY)
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_from_x_forwarded_for():
    req = _make_request(
        "/", headers=[("x-forwarded-for", "5.6.7.8, 10.0.0.1")], client=LOCAL_PROXY
    )
    assert req.remote_ip == "5.6.7.8"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_from_x_real_ip():
    req = _make_request("/", headers=[("x-real-ip", "9.10.11.12")], client=LOCAL_PROXY)
    assert req.remote_ip == "9.10.11.12"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("header", ["forwarded", "x-forwarded-for", "x-real-ip"])
def test_remote_ip_ignores_forwarding_headers_from_an_untrusted_peer(header):
    """Any client can send these headers: only a trusted proxy's count."""
    value = "for=1.2.3.4" if header == "forwarded" else "1.2.3.4"
    req = _make_request("/", headers=[(header, value)], client=("203.0.113.5", 5000))
    assert req.remote_ip == "203.0.113.5"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("header", ["forwarded", "x-forwarded-for", "x-real-ip"])
@pytest.mark.parametrize(
    "client", [None, ("", None), ("unix", None), ("unix:/run/a.sock", None)]
)
def test_remote_ip_uses_forwarding_headers_without_a_peer_address(header, client):
    """A server on a Unix socket gives no peer address: only a process on
    the same machine, such as nginx, can connect to it."""
    value = "for=1.2.3.4" if header == "forwarded" else "1.2.3.4"
    req = _make_request(
        "/", headers=[(header, value), ("x-forwarded-proto", "https")], client=client
    )
    assert req.remote_ip == "1.2.3.4"
    assert req.is_secure is True


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize(
    "peer",
    [
        "127.0.0.1",
        "127.8.9.10",
        "::1",
        "10.1.2.3",
        "172.16.0.1",
        "172.31.255.254",
        "192.168.1.1",
        "169.254.1.1",
        "fc00::1",
        "fdab::1",
        "fe80::1",
        "::ffff:10.0.0.1",
    ],
)
def test_remote_ip_default_trusted_proxies(peer):
    req = _make_request("/", headers=[("x-real-ip", "1.2.3.4")], client=(peer, 5000))
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("peer", ["172.32.0.1", "8.8.8.8", "2001:db8::1", "not-an-ip"])
def test_remote_ip_default_untrusted_peers(peer):
    req = _make_request("/", headers=[("x-real-ip", "1.2.3.4")], client=(peer, 5000))
    assert req.remote_ip == peer


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_skips_trusted_proxies_from_the_right():
    """The client can write anything at the left of the list; the address
    the first untrusted hop connected from is the last it can't fake."""
    req = _make_request(
        "/",
        headers=[("x-forwarded-for", "6.6.6.6, 1.2.3.4 , 10.0.0.2,192.168.0.9")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_all_trusted_is_the_leftmost():
    req = _make_request(
        "/", headers=[("x-forwarded-for", " 10.0.0.3, 10.0.0.2")], client=LOCAL_PROXY
    )
    assert req.remote_ip == "10.0.0.3"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_stops_at_a_value_that_is_not_an_ip():
    req = _make_request(
        "/",
        headers=[("x-forwarded-for", "1.2.3.4, unknown, 10.0.0.2")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "unknown"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_with_ports_and_ipv6():
    req = _make_request(
        "/",
        headers=[
            ("x-forwarded-for", "6.6.6.6, 2001:db8::7, [fc00::2]:443, 10.0.0.2:8080")
        ],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "2001:db8::7"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize(
    "hop, expected",
    [
        # Azure Application Gateway adds the client's port.
        ("203.0.113.5:51234", "203.0.113.5"),
        ("[2001:db8::7]:51234", "2001:db8::7"),
        ("[2001:db8::7]", "2001:db8::7"),
        ("::ffff:203.0.113.5", "203.0.113.5"),
    ],
)
def test_remote_ip_x_forwarded_for_without_the_port(hop, expected):
    req = _make_request(
        "/", headers=[("x-forwarded-for", f"{hop}, 10.0.0.2")], client=LOCAL_PROXY
    )
    assert req.remote_ip == expected


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_forwarded_skips_trusted_proxies_from_the_right():
    req = _make_request(
        "/",
        headers=[
            (
                "forwarded",
                "for=6.6.6.6, for=1.2.3.4:4711;proto=https, by=10.0.0.9, "
                'for="[fc00::1]:80", for=10.0.0.2',
            )
        ],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_forwarded_all_trusted_is_the_leftmost():
    req = _make_request(
        "/", headers=[("forwarded", 'for="[::1]", for=10.0.0.2')], client=LOCAL_PROXY
    )
    assert req.remote_ip == "::1"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize(
    "hop, expected",
    [
        ("1.2.3.4:4711", "1.2.3.4"),
        ('"[2001:db8::7]:4711"', "2001:db8::7"),
        ('"[2001:db8::7]"', "2001:db8::7"),
        ('"[::ffff:203.0.113.5]"', "203.0.113.5"),
        ('"_hidden:4711"', "_hidden:4711"),
    ],
)
def test_remote_ip_forwarded_without_the_port(hop, expected):
    """With the port, the default `rate_limit` key would change with each
    connection the client opens."""
    req = _make_request(
        "/", headers=[("forwarded", f"for={hop}, for=10.0.0.2")], client=LOCAL_PROXY
    )
    assert req.remote_ip == expected


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("client_part", ['for=1.2.3.4;by="x', 'for="r4nd0m-123'])
def test_remote_ip_forwarded_a_quote_the_client_leaves_open(client_part):
    """The client's part of `Forwarded` ends in a quoted string it doesn't
    close. The element the proxy appends has a quoted value (an IPv6
    address, or one with a port), and its first quote must not close the
    client's string: the client would choose `remote_ip`."""
    req = _make_request(
        "/",
        headers=[("forwarded", f'{client_part}, for="[2001:db8::66]:4711";proto=https')],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "2001:db8::66"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize(
    "proxy_part, expected",
    [
        ('host="a,b";for=1.2.3.4', "1.2.3.4"),
        ('by="x,y";for="[2001:db8::66]:4711"', "2001:db8::66"),
        ('host="a\\",b";for=1.2.3.4', "1.2.3.4"),
    ],
)
def test_remote_ip_forwarded_a_comma_in_a_quoted_value_of_the_proxy(proxy_part, expected):
    """A comma inside a quoted value of the proxy's own element doesn't end
    the element: its `for=` must not be lost, or `remote_ip` would be the
    address the client wrote."""
    req = _make_request(
        "/", headers=[("forwarded", f"for=6.6.6.6, {proxy_part}")], client=LOCAL_PROXY
    )
    assert req.remote_ip == expected


@pytest.mark.parametrize(
    "value, elements",
    [
        ("", [""]),
        ("for=1.2.3.4, for=5.6.7.8", ["for=1.2.3.4", " for=5.6.7.8"]),
        ('for=1, host="a,b";for=2', ["for=1", ' host="a,b";for=2']),
        ('for="1, for=2', ['for="1', " for=2"]),
        ('for="1, host="a,b"', ['for="1', ' host="a,b"']),
        ('a="x\\",y", b="\\\\", c', ['a="x\\",y"', ' b="\\\\"', " c"]),
    ],
)
def test_split_forwarded(value, elements):
    assert split_forwarded(value) == elements


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize(
    "name, lines",
    [
        ("x-forwarded-for", ["198.51.100.7", "10.0.0.2"]),
        ("forwarded", ["for=198.51.100.7", "for=10.0.0.2"]),
    ],
)
def test_remote_ip_reads_every_line_of_a_forwarding_header(name, lines):
    """A header sent in several lines is one list, the lines in order (RFC
    9110 §5.3): the client's address can be in an earlier line than the
    trusted proxy's."""
    req = _make_request("/", headers=[(name, line) for line in lines], client=LOCAL_PROXY)
    assert req.remote_ip == "198.51.100.7"


@pytest.mark.usefixtures("no_current_app")
def test_forwarded_reads_every_line():
    req = _make_request(
        "/",
        headers=[("forwarded", "for=1.2.3.4"), ("forwarded", "for=5.6.7.8;proto=https")],
    )
    assert req.forwarded == [{"for": "1.2.3.4"}, {"for": "5.6.7.8", "proto": "https"}]


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_forwarded_obfuscated_identifier():
    req = _make_request(
        "/", headers=[("forwarded", "for=1.2.3.4, for=_hidden")], client=LOCAL_PROXY
    )
    assert req.remote_ip == "_hidden"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_wins_over_forwarded():
    """A proxy that writes only `X-Forwarded-For` (nginx, Caddy, ...) passes a
    `Forwarded` header from the client through untouched."""
    req = _make_request(
        "/",
        headers=[("forwarded", "for=6.6.6.6"), ("x-forwarded-for", "1.2.3.4")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_empty_x_forwarded_for_falls_back():
    req = _make_request(
        "/",
        headers=[("x-forwarded-for", " , "), ("forwarded", "for=1.2.3.4")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_trusted_peer_without_forwarding_headers():
    req = _make_request("/", client=LOCAL_PROXY)
    assert req.remote_ip == "127.0.0.1"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_forwarded_without_for_falls_back():
    req = _make_request(
        "/",
        headers=[("forwarded", "proto=https"), ("x-real-ip", "1.2.3.4")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_without_an_app_uses_the_default_trusted_proxies():
    headers = [("x-forwarded-for", "1.2.3.4")]
    assert _make_request("/", headers=headers, client=LOCAL_PROXY).remote_ip == "1.2.3.4"
    req = _make_request("/", headers=headers, client=("203.0.113.5", 5000))
    assert req.remote_ip == "203.0.113.5"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_custom_trusted_proxies():
    app = App(
        __name__,
        {
            "SECRET_KEYS": ["*" * 50],
            "TRUSTED_PROXIES": ["203.0.113.0/24", "2001:db8::1"],
        },
    )
    headers = [("x-forwarded-for", "1.2.3.4, 203.0.113.8")]

    req = _make_request("/", headers=headers, client=("203.0.113.7", 5000), app=app)
    assert req.remote_ip == "1.2.3.4"
    req = _make_request("/", headers=headers, client=("2001:db8::1", 5000), app=app)
    assert req.remote_ip == "1.2.3.4"
    # The defaults are replaced, not extended.
    req = _make_request("/", headers=headers, client=LOCAL_PROXY, app=app)
    assert req.remote_ip == "127.0.0.1"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_no_trusted_proxies():
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "TRUSTED_PROXIES": []})
    req = _make_request(
        "/", headers=[("forwarded", "for=1.2.3.4")], client=LOCAL_PROXY, app=app
    )
    assert req.remote_ip == "127.0.0.1"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_from_client():
    req = _make_request("/", client=("192.168.1.1", 5000))
    assert req.remote_ip == "192.168.1.1"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_no_client():
    req = _make_request("/")
    assert req.remote_ip == ""


@pytest.mark.usefixtures("no_current_app")
def test_trusted_proxies_set_as_strings_after_the_app_was_created():
    """`TRUSTED_PROXIES` is parsed when the app is created; a list of
    strings set later is parsed when it is used."""
    app = App(__name__, {"SECRET_KEYS": ["*" * 50]})
    app.config.TRUSTED_PROXIES = ["203.0.113.0/24"]
    headers = [("x-forwarded-for", "1.2.3.4"), ("x-forwarded-proto", "https")]

    req = _make_request("/", headers=headers, client=("203.0.113.7", 5000), app=app)
    assert req.remote_ip == "1.2.3.4"
    assert req.is_secure is True
    req = _make_request("/", headers=headers, client=LOCAL_PROXY, app=app)
    assert req.remote_ip == "127.0.0.1"
    assert req.is_secure is False


def test_request_id():
    req = _make_request("/", headers=[("x-request-id", "req-123")])
    assert req.request_id == "req-123"


def test_request_id_missing():
    req = _make_request("/")
    assert req.request_id is None


def test_user_agent():
    req = _make_request("/", headers=[("user-agent", "TestBot/1.0")])
    assert req.user_agent == "TestBot/1.0"


def test_user_agent_missing():
    req = _make_request("/")
    assert req.user_agent is None


@pytest.mark.usefixtures("no_current_app")
def test_protocol_from_x_forwarded_proto():
    req = _make_request(
        "http://example.com/",
        headers=[("x-forwarded-proto", "https")],
        client=LOCAL_PROXY,
    )
    assert req.protocol == "https"
    assert req.is_secure is True


@pytest.mark.usefixtures("no_current_app")
def test_protocol_ignores_x_forwarded_proto_from_an_untrusted_peer():
    req = _make_request(
        "http://example.com/",
        headers=[("x-forwarded-proto", "https")],
        client=("203.0.113.5", 5000),
    )
    assert req.protocol == "http"
    assert req.is_secure is False
    assert req.default_port == 80


@pytest.mark.usefixtures("no_current_app")
def test_protocol_from_x_forwarded_proto_without_a_peer_address():
    """A server on a Unix socket: the peer is a process on the same machine."""
    req = _make_request("http://example.com/", headers=[("x-forwarded-proto", "https")])
    assert req.protocol == "https"
    assert req.is_secure is True
    assert req.default_port == 443


def test_headers_get_missing():
    req = _make_request("/")
    assert req.headers.get("nonexistent") is None


def test_headers_get_string():
    req = _make_request("/")
    req.headers["x-str"] = "string-value"
    assert req.headers.get("x-str") == "string-value"


# --- accept edge cases ---


def test_accept_empty():
    req = _make_request("/")
    assert req.accept == []


def test_accept_quality_sorting():
    req = _make_request(
        "/",
        headers=[
            ("accept", "text/plain;q=0.5,text/html;q=0.9,application/json;q=0.1"),
        ],
    )
    assert req.accept == ["text/html", "text/plain", "application/json"]


def test_accept_default_quality_is_1():
    req = _make_request("/", headers=[("accept", "text/html,text/plain;q=0.5")])
    assert req.accept == ["text/html", "text/plain"]


def test_accept_encoding_empty():
    req = _make_request("/")
    assert req.accept_encoding == []


def test_accept_language_empty():
    req = _make_request("/")
    assert req.accept_language == []


def test_accept_with_quoted_params():
    """Exercise the parse_multivalue slow path (quoted strings)."""
    req = _make_request(
        "/",
        headers=[
            ("accept", 'text/html;level="1",application/json;q=0.5'),
        ],
    )
    assert req.accept[0] == "text/html"
    assert req.accept[1] == "application/json"


def test_accept_with_escaped_quotes():
    """Quoted string with escaped quote inside."""
    req = _make_request(
        "/",
        headers=[
            ("accept", r'text/html;level="foo\"bar",text/plain;q=0.5'),
        ],
    )
    assert req.accept[0] == "text/html"
    assert req.accept[1] == "text/plain"


@pytest.mark.parametrize(
    "header, expected",
    [
        # A parameter without a value is ignored, with or without quotes.
        ("text/html;level,application/json;q=0.5", ["text/html", "application/json"]),
        ('text/html;level,application/json;q="0.5"', ["text/html", "application/json"]),
        # An empty parameter, as after a trailing `;`.
        ("text/html;,application/json;q=0.5", ["text/html", "application/json"]),
        ("application/json;q=0.5,text/html;", ["text/html", "application/json"]),
        # A `q` that isn't a number from 0 to 1 is ignored: the weight is 1.
        ("application/json;q=0.5,text/html;q=abc", ["text/html", "application/json"]),
        ('application/json;q=0.5,text/html;q="abc"', ["text/html", "application/json"]),
        ("application/json;q=0.5,text/html;q=", ["text/html", "application/json"]),
        ("application/json;q=0.5,text/html;q=nan", ["text/html", "application/json"]),
        # A q over 1 counts as 1: a tie, so the order in the header stays.
        ("application/json,text/html;q=2", ["application/json", "text/html"]),
        ("text/html;q=-1,application/json;q=0.5", ["text/html", "application/json"]),
    ],
)
def test_accept_malformed_parameters_are_ignored(header, expected):
    req = _make_request("/", headers=[("accept", header)])
    assert req.accept == expected


@pytest.mark.parametrize(
    "header, expected",
    [
        ("text/html;Q=0.1,application/json", ["application/json", "text/html"]),
        ('text/html;Q=0.1;level="1",application/json', ["application/json", "text/html"]),
        ("text/html;LEVEL;Q=0.1,application/json", ["application/json", "text/html"]),
    ],
)
def test_accept_parameter_names_are_case_insensitive(header, expected):
    """RFC 9110 §5.6.6: parameter names are case-insensitive, so `Q` is `q`."""
    req = _make_request("/", headers=[("accept", header)])
    assert req.accept == expected


def test_accept_language_q_is_case_insensitive():
    req = _make_request("/", headers=[("accept-language", "fr;Q=0.5,en-US")])
    assert req.accept_language == ["en_US", "fr"]


@pytest.mark.parametrize("header", ["a;Level=X;Q=1", 'a;Level="X";Q=1'])
def test_parse_multivalue_lowercases_parameter_names(header):
    assert parse_multivalue(header) == [("a", {"level": "X", "q": "1"})]


def test_accept_language_malformed_q_is_ignored():
    req = _make_request("/", headers=[("accept-language", "fr;q=0.5,en-US;q=x")])
    assert req.accept_language == ["en_US", "fr"]


def test_accept_semicolon_without_equals():
    """Semicolon-separated attribute without =value (slow path)."""
    req = _make_request(
        "/",
        headers=[
            ("accept", '"text/html";level'),
        ],
    )
    # Should still parse without error
    assert len(req.accept) >= 1


# --- if_none_match edge cases ---


def test_if_none_match_empty():
    req = _make_request("/")
    assert req.if_none_match == []


def test_if_none_match_single():
    req = _make_request("/", headers=[("if-none-match", '"etag1"')])
    assert req.if_none_match == ['"etag1"']


def test_if_none_match_whitespace():
    req = _make_request("/", headers=[("if-none-match", '"a", "b"')])
    assert '"a"' in req.if_none_match
    assert '"b"' in req.if_none_match


# --- cookie edge cases ---


def test_cookies_empty_header():
    req = _make_request("/")
    assert req.cookies == {}


def test_cookies_empty_name():
    """Cookie chunk without '=' gets empty name."""
    req = _make_request("/", headers=[("cookie", "justvalue")])
    assert req.cookies[""] == "justvalue"


def test_cookies_quoted_value():
    req = _make_request("/", headers=[("cookie", 'a="quoted"')])
    assert req.cookies["a"] == "quoted"


def test_cookies_empty_pair_skipped():
    req = _make_request("/", headers=[("cookie", "a=1;  ;b=2")])
    assert req.cookies["a"] == "1"
    assert req.cookies["b"] == "2"


# --- host parsing ---


def test_server_none_fallback_to_host_header():
    req = Request(headers=[("host", "example.com:8080")])
    assert req.host == "example.com"
    assert req.port == 8080


def test_allow_no_host():
    req = Request()
    assert req.host == ""


@pytest.mark.parametrize(
    "host_header, server, host, port",
    [
        # The server listens on every address, or on a Unix socket: the name
        # the client asked for is in the `Host` header (PEP 3333).
        ("api.example.com", ("0.0.0.0", 2300), "api.example.com", 80),
        ("api.example.com:8443", ("0.0.0.0", 2300), "api.example.com", 8443),
        ("API.Example.com", ("/run/app.sock", None), "api.example.com", 80),
        ("[2001:db8::1]:8080", ("::", 2300), "2001:db8::1", 8080),
        # Without a `Host` header (HTTP/1.0), or with an empty one, the address
        # the request arrived at.
        (None, ("10.0.0.5", 2300), "10.0.0.5", 2300),
        ("", ("10.0.0.5", 2300), "10.0.0.5", 2300),
        (None, ("10.0.0.5", None), "10.0.0.5", 80),
    ],
)
def test_host_from_the_host_header_else_the_server(host_header, server, host, port):
    headers = [] if host_header is None else [("host", host_header)]
    req = Request(headers=headers, server=server)
    assert (req.host, req.port) == (host, port)


def test_host_with_port_from_the_host_header():
    req = Request(headers=[("host", "example.com:8080")], server=("0.0.0.0", 2300))
    assert req.host_with_port == "example.com:8080"
    req = Request(headers=[("host", "example.com")], server=("0.0.0.0", 2300))
    assert req.host_with_port == "example.com"


@pytest.mark.parametrize(
    "headers, server, expected",
    [
        # An IPv6 address goes back in brackets, as in the `Host` header and the
        # netloc of an `Origin`; the port only when it is not the default one.
        ([("host", "[2606:4700::1]:8080")], None, "[2606:4700::1]:8080"),
        ([("host", "[2606:4700::1]")], None, "[2606:4700::1]"),
        ([("host", "[2606:4700::1]:80")], None, "[2606:4700::1]"),
        ([("host", "[::FFFF:192.0.2.1]:8080")], None, "[::ffff:192.0.2.1]:8080"),
        # Without a `Host` header, the server's address has no brackets.
        ([], ("::1", 8080), "[::1]:8080"),
        ([], ("::1", None), "[::1]"),
        ([("host", "192.0.2.1:8080")], None, "192.0.2.1:8080"),
    ],
)
def test_host_with_port_puts_an_ipv6_address_in_brackets(headers, server, expected):
    req = Request(headers=headers, server=server)
    assert req.host_with_port == expected


@pytest.mark.parametrize("hosts", [["a.com", "b.com"], ["a.com", "a.com"]])
def test_more_than_one_host_header_is_refused(hosts):
    # RFC 9112 §3.2. Bearings joins the lines with a comma; a `Request`
    # built with repeated pairs gets the same answer.
    with pytest.raises(InvalidHeader, match="Host"):
        Request(headers=[("host", host) for host in hosts], server=("0.0.0.0", 2300))


def test_a_host_header_with_an_ipv6_zone_id_is_refused():
    # Proper does not accept an IPv6 zone id (RFC 6874, `%25eth0`) in it.
    with pytest.raises(InvalidHeader, match="Host"):
        Request(headers=[("host", "[fe80::1%25eth0]:8080")])


def test_an_invalid_host_header_is_refused_even_with_a_server():
    with pytest.raises(InvalidHeader, match="Host"):
        Request(headers=[("host", "example.com/x?y")], server=("0.0.0.0", 2300))


def test_host_from_header_ipv6():
    req = Request(headers=[("host", "[::1]")])
    assert req.host == "::1"
    assert req.port == 80  # default


def test_host_from_header_ipv6_with_port():
    req = Request(headers=[("host", "[::1]:9090")])
    assert req.host == "::1"
    assert req.port == 9090


def test_host_from_header_non_decimal_port():
    # A non-numeric port is invalid per RFC 9112 §3.2 / RFC 3986 §3.2.3.
    with pytest.raises(InvalidHeader, match="Host"):
        Request(headers=[("host", "example.com:abc")])


def test_host_from_header_simple():
    req = Request(headers=[("host", "myhost:8080")])
    assert req.host == "myhost"
    assert req.port == 8080


@pytest.mark.parametrize("value", [
    "example.com",
    "example.com:8080",
    "example.com:",  # empty port is allowed by RFC 3986 (port = *DIGIT)
    "sub.example.com",
    "localhost",
    "something.localhost:1234",
    "127.0.0.1",
    "127.0.0.1:5000",
    "[::1]",
    "[::1]:9090",
    "[2001:db8::1]:443",
    "[::ffff:1.2.3.4]",  # an IPv6 address with the IPv4 form at its end
    "my-host_1.example~test",  # unreserved chars
    "xn--80ak6aa92e.com",  # punycode (IDN)
])
def test_accepts_valid_host(value):
    host, _ = parse_host(value)
    print(value)
    assert host is not None


@pytest.mark.parametrize("value", [
    "example.com/abc?bar=",  # X41-2026-002: path/query injection
    "example.com/abc",
    "example.com?x=1",
    "example.com#frag",
    "user@example.com",  # userinfo is not part of a Host header
    "example.com:abc",  # non-numeric port
    "exa mple.com",  # space
    "example.com\n",  # trailing newline (header injection)
    "exam\tple.com",  # control character
    "::1",  # unbracketed IPv6
    "",  # empty
    "a.com,b.com",  # two `Host` lines, joined by the server (RFC 9112 §3.2)
    "a.com, b.com",
    "a.com,",
    "[::1],[::2]",
    # RFC 3986 §3.2.2: an IPv6 address in the brackets, nothing else.
    "[abc]",
    "[1.2.3.4]",
    "[127.0.0.1]:81",
    "[::1::2]",
    "[]",
    "[v1.x]",  # IPvFuture
])
def test_rejects_invalid_host(value):
    with pytest.raises(InvalidHeader, match="Host"):
        print(value)
        host, _ = parse_host(value)


# --- request_id edge cases ---


def test_request_id_truncated():
    long_id = "a" * 300
    req = _make_request("/", headers=[("x-request-id", long_id)])
    assert req.request_id and len(req.request_id) == 200


def test_request_id_non_ascii_removed():
    req = _make_request("/", headers=[("x-request-id", "abc\x80\x81def")])
    assert req.request_id == "abcdef"


# --- forwarded edge cases ---


def test_forwarded_empty():
    req = _make_request("/")
    assert req.forwarded == []


def test_forwarded_multiple_proxies():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4,for=5.6.7.8"),
        ],
    )
    assert len(req.forwarded) == 2
    assert req.forwarded[0]["for"] == "1.2.3.4"
    assert req.forwarded[1]["for"] == "5.6.7.8"


def test_forwarded_quoted_values():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", 'for="1.2.3.4"'),
        ],
    )
    assert req.forwarded[0]["for"] == "1.2.3.4"


def test_forwarded_escaped_quotes():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", r'for="val\"ue"'),
        ],
    )
    assert req.forwarded[0]["for"] == 'val"ue'


def test_forwarded_port_suffix():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4:8080"),
        ],
    )
    assert req.forwarded[0]["for"] == "1.2.3.4:8080"


def test_forwarded_multiple_params():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4;proto=https;by=proxy"),
        ],
    )
    fwd = req.forwarded[0]
    assert fwd["for"] == "1.2.3.4"
    assert fwd["proto"] == "https"
    assert fwd["by"] == "proxy"


def test_forwarded_case_insensitive_keys():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "For=1.2.3.4;Proto=https"),
        ],
    )
    fwd = req.forwarded[0]
    assert fwd["for"] == "1.2.3.4"
    assert fwd["proto"] == "https"


def test_forwarded_whitespace_between_pairs():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4 ; proto=https"),
        ],
    )
    fwd = req.forwarded[0]
    assert fwd["for"] == "1.2.3.4"
    assert fwd["proto"] == "https"


def test_forwarded_bad_syntax_skipped():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "!!!,for=1.2.3.4"),
        ],
    )
    # First proxy is empty (bad syntax skipped), second has the value
    assert req.forwarded[1]["for"] == "1.2.3.4"


def test_forwarded_bad_syntax_after_valid():
    """Two valid pairs without separator → bad syntax, skip to next comma."""
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4 for=bad,for=5.6.7.8"),
        ],
    )
    # After first valid pair, "for=bad" is encountered without separator
    # so it skips to comma, then parses for=5.6.7.8
    assert req.forwarded[0]["for"] == "1.2.3.4"
    assert req.forwarded[1]["for"] == "5.6.7.8"
