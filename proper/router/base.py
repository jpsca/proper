import re
from string import Template
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Optional


__all__ = ("BaseRoute", "MissingParameter", "BadPlaceholder", "BadFormat")


"""Formats to be replaced with regular expressions.
Note that these DOESN'T do any type conversion, just
validates the section of the route match the regular expression.
"""
FORMATS = {
    None: r"[^\/]+",
    "path": r".+",
    "int": r"[0-9]+",
    "float": r"[0-9]+\.[0-9]+",
}

RE_PLACEHOLDERS = re.compile(r":([_a-z][_a-z0-9]*)(?:<([^>]+)>)?")


class MissingParameter(Exception):
    def __init__(self, name: str, path: str) -> None:
        msg = f"missing value for {name} in {path}"
        super().__init__(msg)


class BadPlaceholder(Exception):
    def __init__(self, name: str, path: str, rx: str) -> None:
        msg = f"placeholder {name} doesn't have the expected format <{rx}> in {path}"
        super().__init__(msg)


class DuplicatedPlaceholder(Exception):
    def __init__(self, name: str, path: str) -> None:
        msg = f"placeholder {name} declared more than once in {path}"
        super().__init__(msg)


class BadFormat(Exception):
    pass


class _RouteTemplate(Template):
    delimiter = ":"


class BaseRoute:
    __slots__ = (
        "path",
        "path_re",
        "path_plain",
        "path_placeholders",
    )

    def __init__(self) -> None:
        self.path: str = ""
        self.path_re: "Optional[re.Pattern]" = None
        self.path_plain: "Optional[str]" = None
        self.path_placeholders: dict = {}

    def __eq__(self, other: "Any") -> bool:
        if getattr(other, "__slots__", None) != self.__slots__:
            return NotImplemented
        return all(
            [
                getattr(self, attr, None) == getattr(other, attr, None)
                for attr in self.__slots__
                if not attr.startswith("_") and not attr.startswith("path_")
            ]
        )

    def compile_path(self) -> None:
        path = self.path.rstrip("/")
        parts = []
        parts_re = []
        placeholders = {}
        index = 0

        while True:
            match = RE_PLACEHOLDERS.search(path, pos=index)
            if not match:
                break
            start, end = match.span()
            part = path[index:start]
            parts.append(part)
            parts_re.append(re.escape(part))
            index = end

            name, rx = match.groups()
            if name in placeholders:
                raise DuplicatedPlaceholder(name, path)

            rx = FORMATS.get(rx, rx)
            placeholders[name] = rx
            parts.append(f":{name}")
            parts_re.append(rf"(?P<{name}>{rx})")

        part = path[index:]
        parts.append(part)
        plain = "".join(parts)

        parts_re.append(re.escape(part))
        str_re = r"".join(parts_re) + r"/?$"
        try:
            path_re = re.compile(str_re)
        except Exception as e:
            raise BadFormat(e)

        self.path_re = path_re
        self.path_plain = plain
        self.path_placeholders = placeholders

    def match(self, path: str) -> "Optional[re.Match]":
        if self.path_re is None:
            self.compile_path()

        assert self.path_re
        return self.path_re.match(path)

    def format(self, **kw) -> str:
        if self.path_plain is None:
            self.compile_path()

        tmpl = _RouteTemplate(self.path_plain or "")
        path_params = self._get_path_params(kw)
        url = tmpl.substitute(dict(path_params)) or "/"

        query_params = self._get_query_params(path_params, kw)
        if query_params:
            params = "&".join(
                [key + "=" + value for key, value in query_params.items()]
            )
            url = url + "?" + params

        return url

    def _get_path_params(self, kwargs: dict) -> dict:
        path_params = {}

        for name, rx in self.path_placeholders.items():
            value = kwargs.get(name)
            if value is None:
                raise MissingParameter(name, self.path)
            value = str(value)
            if not re.match(rx, value):
                raise BadPlaceholder(name, self.path, rx)
            path_params[name] = value

        return path_params

    def _get_query_params(self, path_params: dict, kwargs: dict) -> dict:
        query_params = {}

        for name, value in kwargs.items():
            if name not in path_params:
                query_params[name] = value

        return query_params
