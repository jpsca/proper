import re
import typing as t

from .encodict import EncoDict
from .multidict import MultiDict


class Header:
    def __init__(self, name: str, value: str, **params: str) -> None:
        # parse value
        self._name = name.title()
        self._value = value
        self._params = {k.replace("_", "-"): v for k, v in params.items()}
        self._tuple = (self._name, self._render_value())

    @property
    def name(self):
        return self._name

    @property
    def value(self):
        return self._value

    @property
    def params(self):
        return self._params

    @property
    def tuple(self):
        return self._tuple

    def _render_value(self) -> str:
        """Produce a header value and `key=value` parameters separated by semicolons.

        If a value contains non-token characters, it will be quoted.
        If a value is `None`, the parameter is skipped.
        In some keys for some headers, a UTF-8 value can be encoded using a special
        `key*=UTF-8''value` form, where `value` is percent encoded. This function will
        not produce that format automatically, but if a given key ends with an asterisk
        `*`, the value is assumed to have that form and will not be quoted further.
        If a key ends with `*`, its value will not be quoted.

        """
        segments = []

        if self._value is not None:
            segments.append(self._value)

        for key, value in self._params.items():
            if value is None:
                continue
            key = key.replace("_", "-")

            if key[-1] == "*":
                segments.append(f"{key}={value}")
            else:
                segments.append(f"{key}={_quote_header_value(value)}")

        return "; ".join(segments)


class HeaderDict(MultiDict):
    """An object that stores some headers. It has a dict-like interface,
    but is ordered, can store the same key multiple times, and iterating
    yields `(key, value)` pairs instead of only keys.

    This data structure is useful if you want a nicer way to handle WSGI
    headers, which are stored as tuples in a list, and is mostly
    compatible with the Python `wsgiref.headers.Headers`.

    To create a new `Headers` object, pass it a list, dict, or
    other `Headers` object with values. These values are
    validated the same way values added later are.

    """

    def __init__(self, *args, **kwargs):
        self.dict = EncoDict()
        self.dict.encode_key = lambda key: key.strip().lower().replace("_", "-")
        super().__init__(*args, **kwargs)

    def __iter__(self):
        for headers in self.dict.values():
            for header in headers:
                yield header.dump()

    def __getitem__(self, name: str):
        """Get the first header value for 'name'

        Return `None` if the header is missing instead of raising an exception.

        Note that if the header appeared multiple times, the first exactly which
        occurrence gets returned is undefined.  Use getall() to get all
        the values matching a header field name.
        """
        self.get(name)

    def load_environ(self, environ):
        for key, value in environ.items():
            key = key.strip().lower().replace("_", "-")

            if key.startswith("http-") and key not in (
                "http-content-type",
                "http-content-length",
            ):
                key = key[5:]
            elif key in ("content-type", "content-length") and value:
                pass
            else:
                continue

            for hvalue, hparams in _parse_http_header(value):
                self.add(key, hvalue, **hparams)

    def add(self, name: str, value: str, **params) -> None:
        self.append(name, Header(name, value, **params))

    def set(self, name: str, value: str, **params):
        """Replace all header values for `name` and add a new one.
        """
        super().set(name, [Header(name, value, **params)])


#: Header tokenizer used by _parse_http_header()
rx_split = re.compile('(?:(?:"((?:[^"\\\\]|\\\\.)*)")|([^;,=]+))([;,=]?)').findall


def _parse_http_header(header: str) -> list[tuple[str, dict[str, str]]]:
    """Parses a typical multi-valued and parametrised HTTP header
    (e.g. Accept headers) and returns a list of values and parameters.
    For non-standard or broken input, this implementation may return partial results.

    Arguments:
        h: A header string (e.g. ``text/html,text/plain;q=0.9,*/*;q=0.8``)

    Return:
        List of (value, params) tuples. The second element is a
        (possibly empty) dict.
    """
    values = []
    if '"' not in header:  # INFO: Fast path without regexp (~2x faster)
        for value in header.split(','):
            parts = value.split(';')
            values.append((parts[0].strip(), {}))
            for attr in parts[1:]:
                name, value = attr.split('=', 1)
                values[-1][1][name.strip()] = value.strip()
    else:
        lop, key, attrs = ',', None, {}
        for quoted, plain, tok in rx_split(header):
            value = plain.strip() if plain else quoted.replace('\\"', '"')
            if lop == ',':
                attrs = {}
                values.append((value, attrs))
            elif lop == ';':
                if tok == '=':
                    key = value
                else:
                    attrs[value] = ''
            elif lop == '=' and key:
                attrs[key] = value
                key = None
            lop = tok
    return values


def _quote_header_value(value: str) -> str:
    """Add double quotes around a header value. If the header contains
    only ASCII token characters, it will be returned unchanged.
    If the header contains ``"`` or ``\\`` characters, they will be escaped
    with an additional ``\\`` character.
    """
    if not value:
        return '""'

    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'
