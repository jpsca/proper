"""The native parsers of request bodies give what Python's (and
python-multipart's, which Proper used before) give: thousands of generated
inputs, valid and broken."""
import random
from urllib.parse import parse_qs

import pytest
from python_multipart import MultipartParser
from python_multipart.exceptions import FormParserError
from python_multipart.multipart import parse_options_header as pm_parse_options_header

from proper.core.request.formparser import (
    parse_multipart_sync,
    parse_options_header,
    parse_query_string,
    parse_urlencoded,
)
from proper.errors import MultipartError


def as_dict(form):
    return {key: list(values) for key, values in form.items()}


# --- urlencoded ---

PIECES = [
    "a", "b", "name", "x y", "+", "++", "%20", "%2B", "%2b", "%", "%4", "%G1", "%zz", "%%",
    "=", "==", "&", "&&", "%C3%B1", "%E2%82%AC", "%FF", "%C3", "%00", "ñ", "€", "日本",
    "item%5B0%5D%5Bqty%5D", "[]", ";", "?", "#", "%25",
]


def random_query(rnd, n):
    return "".join(rnd.choice(PIECES) for _ in range(n))


@pytest.mark.parametrize("seed", range(5))
def test_query_strings(seed):
    rnd = random.Random(seed)
    for _ in range(2000):
        query = random_query(rnd, rnd.randrange(0, 12))
        expected = parse_qs(query, keep_blank_values=True, encoding="utf-8")
        assert as_dict(parse_query_string(query)) == expected, query


@pytest.mark.parametrize("encoding", ["utf-8", "latin-1"])
def test_urlencoded_bodies(encoding):
    rnd = random.Random(encoding)
    for _ in range(4000):
        text = random_query(rnd, rnd.randrange(0, 12))
        try:
            body = text.encode(encoding)
        except UnicodeEncodeError:
            continue
        expected = parse_qs(text, keep_blank_values=True, encoding=encoding)
        assert as_dict(parse_urlencoded(body, encoding)) == expected, text


# --- header parameters ---

KEYS = ["name", "NAME", " name ", "filename", "FileName", "filename*", "name*", "x", "",
        "boundary", "charset", "filename*0", "filename*1*", "a b"]
VALUES = ['"a"', '"a;b"', "plain", '"with \\"quote\\""', '"back\\\\slash"', "<angle>",
          '"C:\\\\docs\\\\file.txt"', '"\\\\\\\\server\\\\file"', "UTF-8''%E2%82%AC.txt",
          "iso-8859-1'en'%A3", '""', '"', '"unterminated', "", "  spaced  ", "ÃÂ±", "x=y"]


def random_header(rnd):
    head = rnd.choice(["form-data", "text/plain", "Multipart/Form-Data", "", " x "])
    params = []
    for _ in range(rnd.randrange(0, 5)):
        if rnd.random() < 0.1:
            params.append(rnd.choice(KEYS))
        else:
            params.append(f"{rnd.choice(KEYS)}={rnd.choice(VALUES)}")
    sep = rnd.choice(["; ", ";", " ; "])
    return sep.join([head, *params]) + rnd.choice(["", ";", " "])


def by_python_multipart(header):
    if not header:
        return "", {}
    content_type, options = pm_parse_options_header(header)
    return content_type.decode("latin-1").strip().lower(), {
        k.decode("latin-1"): v.decode("latin-1") for k, v in options.items()
    }


def test_header_parameters():
    rnd = random.Random(1)
    checked = 0
    for _ in range(20000):
        header = random_header(rnd)
        try:
            expected = by_python_multipart(header)
        except (UnicodeEncodeError, ValueError, IndexError):
            continue  # python-multipart fails on these; the native code doesn't
        assert parse_options_header(header) == expected, header
        checked += 1
    assert checked > 15000


# --- multipart ---

def safe_decode(data):
    """As Proper decoded a name or a field before: UTF-8, else latin-1."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def by_python_multipart_body(body, boundary, *, max_fields=1000, max_files=1000,
                             max_part_size=2**20):
    """What Proper's parser on python-multipart gave: `[(name, value)]`, a
    file as `(filename, content_type, data)`; `None` for a MultipartError."""
    items, current, headers, header = [], {}, [], [b"", b""]
    counts = {"fields": 0, "files": 0}
    ended = []

    class Refused(Exception):
        pass

    def on_part_begin():
        current.clear()
        current["data"] = b""
        headers.clear()

    def on_header_field(data, start, end):
        header[0] += data[start:end]

    def on_header_value(data, start, end):
        header[1] += data[start:end]

    def on_header_end():
        headers.append((header[0].lower(), header[1]))
        header[0] = header[1] = b""

    def on_headers_finished():
        disposition = next((v for k, v in headers if k == b"content-disposition"), b"")
        if not disposition:
            raise Refused
        _, options = pm_parse_options_header(disposition)
        if b"name" not in options:
            raise Refused
        current["name"] = safe_decode(options[b"name"])
        if b"filename" in options:
            counts["files"] += 1
            if counts["files"] > max_files:
                raise Refused
            current["filename"] = safe_decode(options[b"filename"])
            ctype = next((v for k, v in headers if k == b"content-type"), None)
            current["ctype"] = ctype.decode("latin-1") if ctype is not None else None
        else:
            counts["fields"] += 1
            if counts["fields"] > max_fields:
                raise Refused

    def on_part_data(data, start, end):
        current["data"] += data[start:end]
        if "filename" not in current and len(current["data"]) > max_part_size:
            raise Refused

    def on_part_end():
        if "filename" in current:
            items.append((current["name"], (current["filename"], current["ctype"],
                                            current["data"])))
        else:
            items.append((current["name"], safe_decode(current["data"])))

    parser = MultipartParser(boundary, {
        "on_part_begin": on_part_begin, "on_header_field": on_header_field,
        "on_header_value": on_header_value, "on_header_end": on_header_end,
        "on_headers_finished": on_headers_finished, "on_part_data": on_part_data,
        "on_part_end": on_part_end, "on_end": lambda: ended.append(True),
    })
    try:
        parser.write(body)
        parser.finalize()
    except (Refused, FormParserError):
        return None
    return items if ended else None


def by_proper(body, boundary, **limits):
    try:
        form = parse_multipart_sync(body, {"boundary": boundary}, **limits)
    except MultipartError:
        return None
    items = []
    for name, values in form.items():
        for value in values:
            if isinstance(value, str):
                items.append((name, value))
            else:
                items.append((name, (value.filename, value.content_type, value.raw)))
                value.close()
    return items


def in_order(items):
    """MultiDict groups the values of a name: compare them that way."""
    grouped = {}
    for name, value in items:
        grouped.setdefault(name, []).append(value)
    return grouped


NAMES = ["a", "b", "título", 'with "quote"', "x;y", "日本", ""]
DATA = [b"", b"v", b"hello world", b"\r\n", b"--", b"\r\n--", b"\r\n-", b"line\r\nline",
        "ñandú".encode(), bytes(range(256))]


def random_body(rnd, boundary):
    b = boundary.encode()
    parts = []
    for _ in range(rnd.randrange(0, 5)):
        name = rnd.choice(NAMES).replace('"', '\\"')
        disposition = f'form-data; name="{name}"'
        is_file = rnd.random() < 0.4
        if is_file:
            disposition += f'; filename="{rnd.choice(["a.txt", "ñ.bin", "C:\\\\x\\\\y.txt"])}"'
        lines = [f"Content-Disposition: {disposition}".encode()]
        if is_file and rnd.random() < 0.7:
            lines.append(b"Content-Type: " + rnd.choice([b"text/plain", b"application/octet-stream"]))
        if rnd.random() < 0.2:
            lines.append(b"X-Extra: 1")
        rnd.shuffle(lines)
        data = b"".join(rnd.choice(DATA) for _ in range(rnd.randrange(0, 4)))
        # data that looks like a boundary, but isn't one
        if rnd.random() < 0.3:
            data += b"\r\n--" + b + rnd.choice([b"x", b"-x", b"\rx", b" "])
        parts.append(b"--" + b + b"\r\n" + b"\r\n".join(lines) + b"\r\n\r\n" + data + b"\r\n")
    body = b"".join(parts) + b"--" + b + b"--" + rnd.choice([b"", b"\r\n", b"\r\nepilogue"])
    if rnd.random() < 0.15:
        body = rnd.choice([b"\r\n", b"\n\r\n"]) + body
    return body


def mutate(rnd, body):
    i = rnd.randrange(0, max(1, len(body)))
    kind = rnd.randrange(4)
    if kind == 0:
        return body[:i]  # cut short
    if kind == 1:
        return body[:i] + bytes([rnd.randrange(256)]) + body[i + 1:]  # a byte changed
    if kind == 2:
        return body[:i] + body[i + 1:]  # a byte dropped
    return body[:i] + rnd.choice([b"\r", b"\n", b"-", b":", b";", b'"']) + body[i:]


@pytest.mark.parametrize("seed", range(4))
def test_multipart_bodies(seed):
    rnd = random.Random(seed)
    refused = accepted = 0
    for _ in range(1500):
        boundary = rnd.choice(["testboundary", "----WebKitFormBoundary7MA4YWxkTrZu0gW", "x"])
        body = random_body(rnd, boundary)
        if rnd.random() < 0.5:
            body = mutate(rnd, body)
        limits = {}
        if rnd.random() < 0.2:
            limits = {"max_fields": rnd.randrange(0, 3), "max_files": rnd.randrange(0, 3),
                      "max_part_size": rnd.randrange(0, 20)}
        expected = by_python_multipart_body(body, boundary, **limits)
        got = by_proper(body, boundary, **limits)
        if expected is None:
            assert got is None, body
            refused += 1
        else:
            assert got is not None, body
            assert in_order(got) == in_order(expected), body
            accepted += 1
    assert refused > 200 and accepted > 200


def headers_part(headers, boundary="b"):
    return (f"--{boundary}\r\n".encode() + b"".join(h + b"\r\n" for h in headers)
            + b"\r\nv\r\n" + f"--{boundary}--\r\n".encode())


DISPOSITION = b'Content-Disposition: form-data; name="a"'


@pytest.mark.parametrize("body, accepted", [
    (headers_part([DISPOSITION] + [b"X-H: 1"] * 7), True),  # 8 headers
    (headers_part([DISPOSITION] + [b"X-H: 1"] * 8), False),  # 9
    (headers_part([DISPOSITION, b"X-Long: " + b"x" * (4224 - 8)]), True),  # 4224 bytes
    (headers_part([DISPOSITION, b"X-Long: " + b"x" * (4224 - 7)]), False),  # 4225
    (headers_part([DISPOSITION, b"X-Long:" + b" " * 4300 + b"x"]), False),  # spaces count
    (headers_part([b"X" * 4300 + b": 1", DISPOSITION]), False),  # and so does the name
    (headers_part([DISPOSITION, b"X-Empty:"]), True),
    (headers_part([DISPOSITION, b": no name"]), False),
    (headers_part([DISPOSITION, b"X-Tab:\tvalue"]), True),
    (headers_part([DISPOSITION, b"X Space: 1"]), False),
    (headers_part([b'content-disposition: form-data; name="a"']), True),
    (headers_part([b"Content-Disposition:"]), False),
    (headers_part([b"Content-Disposition: form-data"]), False),
    (headers_part([b"Content-Disposition: form-data; filename=x"]), False),
    (headers_part([b'Content-Disposition: form-data; name="a"; filename*=UTF-8\'\'x']), True),
    (b"\r\n\n" + headers_part([DISPOSITION]), True),  # CR and LF before the first boundary
    (b"preamble" + headers_part([DISPOSITION]), False),
    (b"--b--", True),  # an empty form
    (b"--b-", False),
    (b"--b-x", False),
    (b"--bx\r\n", False),
])
def test_the_limits_and_the_edges(body, accepted):
    expected = by_python_multipart_body(body, "b")
    assert (expected is not None) == accepted
    got = by_proper(body, "b")
    assert (got is not None) == accepted
    if accepted:
        assert in_order(got) == in_order(expected)
