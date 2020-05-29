import re
from string import Template


__all__ = ("BaseRoute", "MissingParameter", "BadParameter", "BadRule")


"""Rules to be replaced with regular expressions.
Note that these DOESN'T do any type conversion, just
validates the section of the route match the regular expression.
"""
SPECIAL_RULES = {"path": r".+", "int": r"[0-9]+", "float": r"[0-9]+\.[0-9]+"}
DEFAULT_RULE = r"[^\/]+"

RE_PARAMS = re.compile(r":\{?([_a-z][_a-z0-9]*)\}?")
RE_PARAMS_ESC = re.compile(r"(:(?:\\\{)?([_a-z][_a-z0-9]*)(?:\\\})?)")


class MissingParameter(Exception):
    pass


class BadParameter(Exception):
    pass


class BadRule(Exception):
    pass


class _RouteTemplate(Template):
    delimiter = ":"


class BaseRoute(object):
    """
    """

    def __init__(self):
        # Make sure all params have a key in the rules
        for param in RE_PARAMS.findall(self.path):
            self.rules.setdefault(param, None)

    def __eq__(self, other):
        if getattr(other, "__slots__", None) != self.__slots__:
            return NotImplemented
        return all(
            [
                getattr(self, attr) == getattr(other, attr)
                for attr in self.__slots__
                if not attr.startswith("_")
            ]
        )

    def compile_path(self):
        # py36 incorrectly escapes the colon
        path = re.escape(self.path.rstrip("/")).replace("\\:", ":")

        for placeholder, name in RE_PARAMS_ESC.findall(path):
            rule = self.rules.get(name) or DEFAULT_RULE
            rule = SPECIAL_RULES.get(rule, rule)
            path = path.replace(placeholder, rf"(?P<{name}>{rule})")

        try:
            self._re_path = re.compile(rf"^{path}" + r"/?$")
        except Exception as e:
            raise BadRule(e)

        return self._re_path  # For easier testing

    def match(self, path):
        return self._re_path.match(path)

    def format(self, **kwargs):
        tmpl = _RouteTemplate(self.path)

        path_params = self._get_path_params(kwargs)
        url = tmpl.substitute(dict(path_params))
        query_params = self._get_query_params(path_params, kwargs)
        if query_params:
            params = "&".join(
                [key + "=" + value for key, value in query_params.items()]
            )
            url = url + "?" + params

        return url

    def _get_path_params(self, kwargs):
        path_params = {}

        for key, rule in self.rules.items():
            value = kwargs.get(key)
            self._validate_value_exist(key, value)
            value = str(value)
            self._validate_value_format(key, value, rule)
            path_params[key] = value

        return path_params

    def _validate_value_exist(self, key, value):
        if value is None:
            raise MissingParameter(f"missing value for {key} in {self.path}")

    def _validate_value_format(self, key, value, rule):
        rx = SPECIAL_RULES.get(rule) or rule or DEFAULT_RULE
        if not re.match(rx, value):
            raise BadParameter(f"param {key} doesn't have the expected format")

    def _get_query_params(self, path_params, kwargs):
        query_params = {}
        path_keys = path_params.keys()
        for key, value in kwargs.items():
            if key not in path_keys:
                query_params[key] = value
        return query_params
